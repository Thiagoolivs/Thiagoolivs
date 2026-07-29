"""Criação de tabelas e dados iniciais (idempotente)."""
from datetime import date

from .data import DEFAULT_HABITS
from .database import Base, SessionLocal, engine
from .models import Player, Settings


def init_db() -> None:
    """Cria as tabelas e semeia configurações + dois jogadores, se vazio."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.get(Settings, 1) is None:
            db.add(Settings(
                id=1,
                start_date=date.today(),
                duration_days=30,
                fixed_habits=DEFAULT_HABITS,
            ))

        if db.query(Player).count() == 0:
            db.add_all([
                Player(name="Jogador 1", avatar="🦊", objetivo="Evoluir todo dia"),
                Player(name="Jogador 2", avatar="🐨", objetivo="Constância acima de tudo"),
            ])

        db.commit()
    finally:
        db.close()
