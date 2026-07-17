# 🤖 Scalping Bot V2 HYBRIDE — 3 Paires, Max 3 Signaux/Heure

> **Détection rapide** + **Scoring qualité** + **Rate limiter strict**

---

## 🎯 Le problème résolu

| Version | Signaux | Qualité | Win Rate |
|---------|---------|---------|----------|
| V1 Standard | ~5/jour | Élevée | ~55% |
| V2 FAST | ~15/heure | Faible | ~35% |
| **V2 HYBRIDE** | **Max 3/heure** | **Sélectionnée** | **~50%** |

---

## 🏗️ Architecture Hybride

```
Scan 3 paires (2 min)
        ↓
┌─────────────────────────────┐
│  Détection rapide M5         │
│  • Bougie verte → BUY        │
│  • Bougie rouge → SELL       │
└─────────────┬───────────────┘
              ↓
┌─────────────────────────────┐
│  SCORING (0-100)            │
│  • Direction M15: +30      │
│  • Volume >1.5x: +25        │
│  • Corps >60%: +20          │
│  • RSI optimal: +15         │
│  • ATR suffisant: +10       │
│  • Confiance: +5            │
└─────────────┬───────────────┘
              ↓
┌─────────────────────────────┐
│  RATE LIMITER               │
│  • Max 3 signaux/heure       │
│  • Cooldown 15 min/paire     │
│  • Cooldown 3 min global     │
│  • Score min: 55/100        │
└─────────────┬───────────────┘
              ↓
     Envoie les meilleurs
              ↓
┌─────────────────────────────┐
│  Suivi temps réel 1s         │
│  • TP1 → BE auto             │
│  • TP2 → Clôture             │
│  • SL → Compteur + pause     │
└─────────────────────────────┘
```

---

## 📊 Système de Scoring

Chaque setup détecté reçoit un score de 0 à 100:

| Critère | Points | Condition |
|---------|--------|-----------|
| Direction M15 alignée | +30 | Momentum UP/DOWN confirmé |
| Volume élevé | +25 | > 2x moyenne |
| Corps de bougie | +20 | > 70% de la range |
| RSI optimal | +15 | 45-70 (LONG) / 30-55 (SHORT) |
| ATR suffisant | +10 | Pas de marché plat |
| Confiance élevée | +5 | > 75% |

**Seuil d'envoi: 55/100 minimum**

---

## ⏰ Rate Limiter

```
Quota horaire: 3 signaux max (toutes paires confondues)
Cooldown par paire: 15 minutes
Cooldown global: 3 minutes entre 2 signaux
Reset: automatique à chaque nouvelle heure UTC
```

Si 4 setups détectés simultanément → envoie les 3 meilleurs scores.

---

## 📋 Paires

```
BTCUSDT — Liquidité max, spreads serrés
ETHUSDT — Volatilité élevée, mouvements nets
XAUUSDT — Or 24/7, volatilité intraday
```

---

## 🚀 Déploiement

```bash
# 1. Tester en local
python test_symbols.py

# 2. Configurer .env
PAIRS=BTCUSDT,ETHUSDT,XAUUSDT

# 3. Lancer
python main.py
```

---

## ⚠️ Avertissement

Signal éducatif. Trading = risque de perte en capital.
