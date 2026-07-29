"""API do Questly (FastAPI)."""
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import scoring
from .data import CATEGORY_EMOJI, HABITS_MENU, SURPRISE_POOL
from .database import get_db
from .models import DayEntry, Player, Settings
from .schemas import PlayerUpdate, SettingsUpdate, ToggleRequest
from .seed import init_db

app = FastAPI(title="Questly API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Inicializa o banco (idempotente) já no carregamento do módulo, para funcionar
# com qualquer runner ASGI e também nos testes.
init_db()


# --- helpers ---------------------------------------------------------------
def get_settings(db: Session) -> Settings:
    settings = db.get(Settings, 1)
    if settings is None:
        raise HTTPException(500, "Configurações não inicializadas.")
    return settings


def parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, f"Data inválida: {value!r} (use YYYY-MM-DD).")


def get_player(db: Session, player_id: int) -> Player:
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(404, "Jogador não encontrado.")
    return player


def entries_by_date(player: Player) -> dict:
    return {e.date: e for e in player.days}


def days_for(settings: Settings, player: Player, today: date) -> list[dict]:
    return scoring.build_days(settings, entries_by_date(player), today)


def player_payload(settings: Settings, player: Player, today: date) -> dict:
    days = days_for(settings, player, today)
    stats = scoring.player_stats(settings, days, today)
    today_cd = next((cd for cd in days if cd["date"] == today.isoformat()), None)
    return {
        "id": player.id,
        "name": player.name,
        "avatar": player.avatar,
        "objetivo": player.objetivo,
        "peso": player.peso,
        "stats": stats,
        "today": today_cd,
        "_days": days,  # uso interno (removido antes de responder quando preciso)
    }


def casal_perfect_days(settings: Settings, players: list[Player], today: date) -> int:
    """Quantidade de datas em que TODOS os jogadores tiveram dia perfeito."""
    if len(players) < 2:
        return 0
    per_player = [
        {cd["date"]: cd["perfect"] for cd in days_for(settings, p, today)}
        for p in players
    ]
    dates = set(per_player[0])
    for pp in per_player[1:]:
        dates &= set(pp)
    return sum(1 for d in dates if all(pp.get(d) for pp in per_player))


# --- rotas -----------------------------------------------------------------
@app.get("/")
def root():
    return {"app": "Questly", "version": "0.1.0", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/settings")
def read_settings(db: Session = Depends(get_db)):
    s = get_settings(db)
    return {
        "start_date": s.start_date.isoformat(),
        "duration_days": s.duration_days,
        "water_goal_l": s.water_goal_l,
        "steps_goal": s.steps_goal,
        "protein_goal_g": s.protein_goal_g,
        "calories_goal": s.calories_goal,
        "sleep_goal_h": s.sleep_goal_h,
        "rest_days": s.rest_days,
        "spiritual_enabled": s.spiritual_enabled,
        "surprise_frequency": s.surprise_frequency,
        "fixed_habits": s.fixed_habits,
        "habits_menu": HABITS_MENU,
    }


@app.put("/api/settings")
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    s = get_settings(db)
    data = payload.model_dump(exclude_unset=True)
    if "fixed_habits" in data and data["fixed_habits"] is not None:
        data["fixed_habits"] = [h.model_dump() if hasattr(h, "model_dump") else h
                                for h in payload.fixed_habits]
    for field, value in data.items():
        setattr(s, field, value)
    db.commit()
    return read_settings(db)


@app.get("/api/players")
def list_players(db: Session = Depends(get_db)):
    settings = get_settings(db)
    today = date.today()
    players = db.query(Player).order_by(Player.id).all()
    out = []
    for p in players:
        payload = player_payload(settings, p, today)
        payload.pop("_days", None)
        out.append(payload)
    return out


@app.get("/api/players/{player_id}")
def read_player(player_id: int, db: Session = Depends(get_db)):
    settings = get_settings(db)
    player = get_player(db, player_id)
    payload = player_payload(settings, player, date.today())
    payload.pop("_days", None)
    return payload


@app.put("/api/players/{player_id}")
def update_player(player_id: int, payload: PlayerUpdate, db: Session = Depends(get_db)):
    player = get_player(db, player_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(player, field, value)
    db.commit()
    settings = get_settings(db)
    result = player_payload(settings, player, date.today())
    result.pop("_days", None)
    return result


@app.get("/api/challenges/today")
def challenges_today(day: str | None = None, db: Session = Depends(get_db)):
    settings = get_settings(db)
    d = parse_date(day)
    return {
        "date": d.isoformat(),
        "day_number": scoring.day_number(settings, d),
        "duration_days": settings.duration_days,
        "daily": scoring.daily_challenge(settings, d),
        "surprise": scoring.surprise_challenge(settings, d),
    }


@app.get("/api/day/{player_id}")
def read_day(player_id: int, day: str | None = None, db: Session = Depends(get_db)):
    settings = get_settings(db)
    player = get_player(db, player_id)
    d = parse_date(day)
    entry = next((e for e in player.days if e.date == d), None)
    return scoring.compute_day(settings, entry, d)


@app.post("/api/day/{player_id}/toggle")
def toggle(player_id: int, req: ToggleRequest, db: Session = Depends(get_db)):
    settings = get_settings(db)
    player = get_player(db, player_id)
    d = parse_date(req.date)

    entry = next((e for e in player.days if e.date == d), None)
    if entry is None:
        entry = DayEntry(player_id=player.id, date=d, habits_done=[])
        db.add(entry)
        db.flush()

    if req.type == "habit":
        if not req.habit_key:
            raise HTTPException(400, "habit_key é obrigatório para type='habit'.")
        current = list(entry.habits_done or [])
        if req.habit_key in current:
            current.remove(req.habit_key)
        else:
            current.append(req.habit_key)
        entry.habits_done = current
    elif req.type == "daily":
        entry.daily_done = not entry.daily_done
    elif req.type == "surprise":
        entry.surprise_done = not entry.surprise_done

    db.commit()
    db.refresh(player)

    today = date.today()
    days = days_for(settings, player, today)
    stats = scoring.player_stats(settings, days, today)
    day_cd = scoring.compute_day(settings, entry, d)
    return {"day": day_cd, "stats": stats}


@app.get("/api/history/{player_id}")
def history(player_id: int, db: Session = Depends(get_db)):
    settings = get_settings(db)
    player = get_player(db, player_id)
    today = date.today()
    days = days_for(settings, player, today)
    stats = scoring.player_stats(settings, days, today)
    calendar = [
        {
            "date": cd["date"],
            "day_number": cd["day_number"],
            "points": cd["points"],
            "max_points": cd["max_points"],
            "completed": cd["completed"],
            "perfect": cd["perfect"],
            "category": cd["daily"]["category"],
        }
        for cd in days
    ]
    return {"stats": stats, "calendar": calendar}


@app.get("/api/achievements/{player_id}")
def achievements(player_id: int, db: Session = Depends(get_db)):
    settings = get_settings(db)
    player = get_player(db, player_id)
    today = date.today()
    players = db.query(Player).order_by(Player.id).all()
    days = days_for(settings, player, today)
    stats = scoring.player_stats(settings, days, today)
    casal = casal_perfect_days(settings, players, today)
    return {"achievements": scoring.achievements_for(days, stats, casal)}


@app.get("/api/ranking")
def ranking(db: Session = Depends(get_db)):
    settings = get_settings(db)
    today = date.today()
    players = db.query(Player).order_by(Player.id).all()
    rows = []
    for p in players:
        payload = player_payload(settings, p, today)
        payload.pop("_days", None)
        rows.append(payload)
    rows.sort(key=lambda r: r["stats"]["total"], reverse=True)
    return {"ranking": rows, "casal_perfect_days": casal_perfect_days(settings, players, today)}


@app.get("/api/state")
def state(db: Session = Depends(get_db)):
    """Payload agregado que abastece a tela inicial em uma única chamada."""
    settings = get_settings(db)
    today = date.today()
    players = db.query(Player).order_by(Player.id).all()

    player_rows = []
    for p in players:
        payload = player_payload(settings, p, today)
        payload.pop("_days", None)
        player_rows.append(payload)

    leaderboard = sorted(player_rows, key=lambda r: r["stats"]["total"], reverse=True)

    return {
        "date": today.isoformat(),
        "day_number": scoring.day_number(settings, today),
        "duration_days": settings.duration_days,
        "spiritual_enabled": settings.spiritual_enabled,
        "daily": scoring.daily_challenge(settings, today),
        "surprise": scoring.surprise_challenge(settings, today),
        "players": player_rows,
        "leaderboard": leaderboard,
        "casal_perfect_days": casal_perfect_days(settings, players, today),
        "category_emoji": CATEGORY_EMOJI,
        "surprise_pool_size": len(SURPRISE_POOL),
    }
