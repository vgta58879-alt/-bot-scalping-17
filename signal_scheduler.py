"""Signal Scheduler — Garantit exactement 3 signaux/heure UTC.

LOGIQUE:
1. Collecte TOUS les setups détectés dans l'heure
2. Trie par score qualité
3. Sélectionne les 3 meilleurs
4. Les envoie répartis dans l'heure (pas tous d'un coup)
5. Si pas assez de signaux de qualité → baisse le seuil adaptativement
6. Si trop de signaux → garde les 3 meilleurs

RÉPARTITION DANS L'HEURE:
- Slot 1: 00:00 - 20:00 UTC
- Slot 2: 20:00 - 40:00 UTC
- Slot 3: 40:00 - 60:00 UTC
Le bot envoie un signal dès qu'un bon setup est détecté dans son slot.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from time_utils import now_utc, get_current_hour_utc, get_current_minute_utc, format_utc_full
from utils import logger, load_json, save_json
from config import config


class SignalScheduler:
    """Garantit exactement 3 signaux par heure UTC."""

    def __init__(self):
        self.state_file = f"{config.DATA_DIR}/signal_scheduler.json"
        self.state = load_json(self.state_file, {
            "current_hour_utc": get_current_hour_utc(),
            "signals_sent_this_hour": 0,
            "signals_queue": [],
            "all_detected_this_hour": [],
            "hourly_stats": {},
            "min_score_threshold": 55,
        })
        self.target_per_hour = 3
        self.slots = [0, 20, 40]  # Minutes de début de chaque slot
        self._cleanup()

    def _save(self):
        save_json(self.state_file, self.state)

    def _cleanup(self):
        """Reset si nouvelle heure UTC."""
        current_hour = get_current_hour_utc()
        if current_hour != self.state.get("current_hour_utc", -1):
            # Sauvegarder stats de l'heure précédente
            prev_hour = self.state.get("current_hour_utc", 0)
            self.state["hourly_stats"][str(prev_hour)] = {
                "sent": self.state.get("signals_sent_this_hour", 0),
                "detected": len(self.state.get("all_detected_this_hour", [])),
                "threshold_used": self.state.get("min_score_threshold", 55),
            }
            # Reset
            self.state["current_hour_utc"] = current_hour
            self.state["signals_sent_this_hour"] = 0
            self.state["all_detected_this_hour"] = []
            self.state["signals_queue"] = []
            self.state["min_score_threshold"] = 55
            self._save()
            logger.info(f"🔄 Scheduler reset — Nouvelle heure UTC {current_hour:02d}:00")

    def get_current_slot(self):
        """Retourne le slot actuel (0,1,2) et les minutes restantes."""
        minute = get_current_minute_utc()
        if minute < 20:
            return 0, 20 - minute
        elif minute < 40:
            return 1, 40 - minute
        else:
            return 2, 60 - minute

    def get_remaining_slots(self):
        """Retourne les slots restants dans l'heure."""
        current_slot, _ = self.get_current_slot()
        return list(range(current_slot, 3))

    def get_signals_needed(self):
        """Combien de signaux il manque pour atteindre 3."""
        self._cleanup()
        return max(0, self.target_per_hour - self.state["signals_sent_this_hour"])

    def add_detected(self, signal, score):
        """Ajoute un setup détecté à la liste de l'heure."""
        self._cleanup()
        signal["_score"] = score
        self.state["all_detected_this_hour"].append(signal)
        self._save()

    def adapt_threshold(self):
        """Ajuste le seuil de score pour garantir 3 signaux.

        Logique:
        - Si on a déjà 3+ signaux de qualité → seuil reste à 55
        - Si on a 2 signaux et on est au slot 2 → baisse à 45
        - Si on a 0 signal et on est au slot 2 → baisse à 40
        - Si on a 1 signal et on est au slot 3 → baisse à 35
        - Si on a 0 signal et on est au slot 3 → baisse à 35
        - Si on a 2 signaux et on est au slot 3 → baisse à 35
        """
        self._cleanup()
        detected = self.state.get("all_detected_this_hour", [])
        sent = self.state.get("signals_sent_this_hour", 0)
        current_slot, _ = self.get_current_slot()

        needed = self.target_per_hour - sent
        if needed <= 0:
            self.state["min_score_threshold"] = 55
            self._save()
            return 55  # Déjà assez envoyé

        # Compter les signaux déjà envoyés + en attente de qualité suffisante
        high_quality = [s for s in detected if s.get("_score", 0) >= 55]
        medium_quality = [s for s in detected if 45 <= s.get("_score", 0) < 55]
        low_quality = [s for s in detected if 35 <= s.get("_score", 0) < 45]

        # Vérifier si on a assez de signaux en stock
        available = max(0, len(high_quality) - sent)
        if available >= needed:
            self.state["min_score_threshold"] = 55
            self._save()
            return 55  # Assez de signaux de qualité non encore envoyés

        # Pas assez de signaux de qualité → adapter le seuil
        if current_slot == 0:
            # Début d'heure, on peut attendre
            self.state["min_score_threshold"] = 55
            self._save()
            return 55
        elif current_slot == 1:
            # Milieu d'heure, on baisse un peu
            if available + len(medium_quality) >= needed:
                logger.info(f"📉 Seuil adapté: 55 → 45 (slot 2, besoin {needed})")
                self.state["min_score_threshold"] = 45
                self._save()
                return 45
            else:
                logger.info(f"📉 Seuil adapté: 55 → 40 (slot 2, manque signaux)")
                self.state["min_score_threshold"] = 40
                self._save()
                return 40
        else:  # current_slot == 2
            # Fin d'heure, on baisse beaucoup pour atteindre le quota
            if available + len(medium_quality) >= needed:
                logger.info(f"📉 Seuil adapté: 55 → 45 (slot 3, besoin {needed})")
                self.state["min_score_threshold"] = 45
                self._save()
                return 45
            elif available + len(medium_quality) + len(low_quality) >= needed:
                logger.info(f"📉 Seuil adapté: 55 → 35 (slot 3, urgent)")
                self.state["min_score_threshold"] = 35
                self._save()
                return 35
            else:
                logger.info(f"📉 Seuil adapté: 55 → 30 (slot 3, critique)")
                self.state["min_score_threshold"] = 30
                self._save()
                return 30

    def select_signals_to_send(self, count=3):
        """Sélectionne les N meilleurs signaux de la file d'attente.

        Returns:
            Liste des signaux sélectionnés (triés par score décroissant)
        """
        self._cleanup()
        detected = self.state.get("all_detected_this_hour", [])
        if not detected:
            return []
        detected.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return detected[:count]

    def get_pending_signals(self, threshold=55, count=3):
        """Retourne les meilleurs signaux NON ENCORE ENVOYÉS avec score >= threshold.

        Cette méthode regarde TOUTE l'heure (pas seulement le scan actuel).
        """
        self._cleanup()
        detected = self.state.get("all_detected_this_hour", [])
        if not detected:
            return []

        # Filtrer les signaux déjà envoyés (register_sent ajoute "sent_at")
        pending = [s for s in detected if "sent_at" not in s]
        # Filtrer par seuil
        pending = [s for s in pending if s.get("_score", 0) >= threshold]
        # Trier par score décroissant
        pending.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return pending[:count]

    def should_send_now(self, signal, score):
        """Détermine si un signal doit être envoyé MAINTENANT.

        Logique:
        - Vérifier quota horaire
        - Vérifier slot actuel
        - Vérifier cooldown global (3 min)
        """
        self._cleanup()

        # Quota atteint ?
        if self.state["signals_sent_this_hour"] >= self.target_per_hour:
            return False, "Quota 3/heure atteint"

        # Vérifier cooldown global (3 min entre signaux)
        queue = self.state.get("signals_queue", [])
        if queue:
            last_sent_time = queue[-1].get("sent_at")
            if last_sent_time:
                try:
                    last_dt = datetime.fromisoformat(last_sent_time)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    elapsed = (now_utc() - last_dt).total_seconds()
                    if elapsed < 180:
                        return False, f"Cooldown: {int(180 - elapsed)}s"
                except Exception:
                    pass

        # Vérifier slot
        current_slot, minutes_left = self.get_current_slot()
        needed = self.get_signals_needed()
        remaining_slots = self.get_remaining_slots()

        if needed == 0:
            return False, "Quota atteint"

        # Si on est au dernier slot et il reste des signaux à envoyer → envoyer dès que possible
        if current_slot == 2 and needed > 0:
            return True, "Dernier slot, envoi immédiat"

        sent = self.state["signals_sent_this_hour"]

        # Si on est au slot 1 et on a déjà envoyé 2 signaux → attendre slot 2
        # Si on est au slot 1 et on a déjà envoyé 1 signal → attendre slot 2
        # Si on est au slot 2 et on a envoyé 2 signaux → envoyer dès que possible
        if sent >= current_slot + 1:
            return False, f"Slot {current_slot+1} déjà utilisé ({sent}/{needed} envoyés)"

        return True, f"Slot {current_slot+1} disponible"

    def register_sent(self, signal):
        """Marque un signal comme envoyé."""
        self._cleanup()
        self.state["signals_sent_this_hour"] += 1
        signal["sent_at"] = now_utc().isoformat()
        self.state["signals_queue"].append(signal)
        self._save()
        logger.info(f"📤 Signal enregistré: {self.state['signals_sent_this_hour']}/3 cette heure")

    def get_stats(self):
        """Stats du scheduler."""
        self._cleanup()
        current_slot, minutes_left = self.get_current_slot()
        needed = self.get_signals_needed()
        return {
            "hour": self.state["current_hour_utc"],
            "sent": self.state["signals_sent_this_hour"],
            "needed": needed,
            "current_slot": current_slot + 1,
            "minutes_left_in_slot": minutes_left,
            "slots_remaining": self.get_remaining_slots(),
            "threshold": self.state.get("min_score_threshold", 55),
            "detected": len(self.state.get("all_detected_this_hour", [])),
        }


signal_scheduler = SignalScheduler()
