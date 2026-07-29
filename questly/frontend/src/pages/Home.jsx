import { useState } from 'react'
import { useApp } from '../store.jsx'
import { api } from '../api.js'
import PlayerSwitch from '../components/PlayerSwitch.jsx'
import ProgressRing from '../components/ProgressRing.jsx'

export default function Home() {
  const { state, me, playerId, refresh, loading, error } = useApp()
  const [busy, setBusy] = useState(false)

  if (loading) return <div className="screen center muted">Carregando…</div>
  if (error)
    return (
      <div className="screen center">
        <p className="error">Não consegui falar com a API 😕</p>
        <p className="muted small">{error}</p>
        <p className="muted small">Confira se o backend está rodando em {api.BASE}</p>
        <button className="btn" onClick={refresh}>Tentar de novo</button>
      </div>
    )
  if (!state || !me) return <div className="screen center muted">Sem dados.</div>

  const today = me.today
  const daily = today.daily
  const surprise = today.surprise

  async function toggle(body) {
    if (busy) return
    setBusy(true)
    try {
      await api.toggle(playerId, { date: state.date, ...body })
      await refresh()
    } catch (e) {
      alert('Erro ao salvar: ' + e.message)
    } finally {
      setBusy(false)
    }
  }

  const leader = state.leaderboard[0]
  const someoneLeads =
    state.leaderboard.length > 1 &&
    state.leaderboard[0].stats.total > state.leaderboard[1].stats.total

  return (
    <div className="screen">
      <header className="topbar">
        <div>
          <div className="brand">
            <span className="brand-mark">🎯</span> Questly
          </div>
          <div className="muted small">
            Dia {state.day_number} de {state.duration_days} ·{' '}
            {new Date(state.date + 'T00:00').toLocaleDateString('pt-BR', {
              weekday: 'long',
              day: '2-digit',
              month: 'short',
            })}
          </div>
        </div>
        <div className="streak-chip" title="Sequência atual">
          🔥 {me.stats.streak}
        </div>
      </header>

      <PlayerSwitch />

      {/* Ranking */}
      <section className="card leaderboard">
        <div className="card-title">🏆 Ranking</div>
        {state.leaderboard.map((p, i) => (
          <div className="rank-row" key={p.id}>
            <div className="rank-pos">{i === 0 && someoneLeads ? '👑' : i + 1}</div>
            <div className="rank-avatar">{p.avatar}</div>
            <div className="rank-main">
              <div className="rank-name">{p.name}</div>
              <div className="bar">
                <div
                  className="bar-fill"
                  style={{ width: `${p.stats.possible ? (p.stats.total / p.stats.possible) * 100 : 0}%` }}
                />
              </div>
            </div>
            <div className="rank-meta">
              <div className="rank-total">{p.stats.total}</div>
              <div className="muted xsmall">🔥 {p.stats.streak} · ⭐ {p.stats.perfect_days}</div>
            </div>
          </div>
        ))}
        {state.casal_perfect_days > 0 && (
          <div className="couple-note">💞 Casal Inabalável: {state.casal_perfect_days} dia(s) perfeito(s) juntos!</div>
        )}
      </section>

      {/* Progresso de hoje */}
      <section className="card center">
        <div className="card-title self-start">Progresso de hoje</div>
        <ProgressRing value={today.points} max={today.max_points}>
          <div className="ring-value">{today.points}</div>
          <div className="muted xsmall">de {today.max_points} pts</div>
        </ProgressRing>
        <div className="mini-stats">
          <div><b>{me.stats.today}</b><span className="muted xsmall">hoje</span></div>
          <div><b>{me.stats.weekly}</b><span className="muted xsmall">semana</span></div>
          <div><b>{me.stats.total}</b><span className="muted xsmall">total</span></div>
          <div><b>{me.stats.completion_pct}%</b><span className="muted xsmall">conclusão</span></div>
        </div>
      </section>

      {/* Desafio do dia */}
      <section className={'card challenge ' + (today.daily_done ? 'done' : '')}>
        <div className="challenge-head">
          <span className="tag">{daily.emoji} {daily.category}</span>
          <span className="pts">+30 pts</span>
        </div>
        <div className="card-title">Desafio do dia</div>
        <p className="challenge-text">{daily.text}</p>
        <button
          className={'btn full ' + (today.daily_done ? 'btn-done' : 'btn-primary')}
          disabled={busy}
          onClick={() => toggle({ type: 'daily' })}
        >
          {today.daily_done ? '✓ Concluído' : 'Marcar como concluído'}
        </button>
      </section>

      {/* Surpresa */}
      {surprise && (
        <section className={'card surprise ' + (today.surprise_done ? 'done' : '')}>
          <div className="challenge-head">
            <span className="tag hot">🔥 Surpresa</span>
            <span className="pts">+20 pts</span>
          </div>
          <p className="challenge-text">{surprise.text}</p>
          <button
            className={'btn full ' + (today.surprise_done ? 'btn-done' : 'btn-hot')}
            disabled={busy}
            onClick={() => toggle({ type: 'surprise' })}
          >
            {today.surprise_done ? '✓ Encarada!' : 'Aceitar desafio'}
          </button>
        </section>
      )}

      {/* Hábitos fixos */}
      <section className="card">
        <div className="card-title">
          Hábitos de hoje <span className="muted small">({today.n_done}/{today.n_habits})</span>
        </div>
        <div className="habits">
          {today.habits.map((h) => {
            const done = today.habits_done.includes(h.key)
            return (
              <button
                key={h.key}
                className={'habit ' + (done ? 'done' : '')}
                disabled={busy}
                onClick={() => toggle({ type: 'habit', habit_key: h.key })}
              >
                <span className="habit-emoji">{h.emoji}</span>
                <span className="habit-label">{h.label}</span>
                <span className={'check ' + (done ? 'on' : '')}>{done ? '✓' : ''}</span>
              </button>
            )
          })}
        </div>
        {today.perfect && <div className="perfect-banner">⭐ Dia perfeito! +{today.bonus} de bônus</div>}
      </section>
    </div>
  )
}
