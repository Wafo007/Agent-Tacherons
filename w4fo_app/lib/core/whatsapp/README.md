# Intégration WhatsApp — lecture & réponse on-device

## ⚠️ Ce n'est PAS une intégration Meta WhatsApp Cloud API officielle

Cette fonctionnalité a été délibérément pivotée, après confirmation explicite
de l'utilisateur, depuis l'architecture Meta Cloud API initialement prévue
vers une automatisation **100% locale, sur l'appareil de l'utilisateur**,
pour la raison technique suivante : **l'API officielle de Meta ne peut
jamais piloter un numéro WhatsApp personnel déjà utilisé dans l'app grand
public** — elle exige un numéro professionnel dédié, migré et "headless".
Voir l'échange de confirmation avec l'utilisateur (mission précédente) pour
le détail des options présentées avant ce choix.

## Architecture réelle

```
WhatsApp (app personnelle, sur le téléphone)
    ↓ (Paul envoie un message)
Notification système Android postée par com.whatsapp
    ↓
WafoNotificationListenerService (Kotlin, NotificationListenerService — API Android officielle)
    - extrait expéditeur + texte
    - mémorise l'action "Répondre" (RemoteInput + PendingIntent) de CETTE notification
    ↓ (EventChannel, uniquement vers le moteur Flutter du PREMIER PLAN)
WhatsAppNotifier (Riverpod)
    - ajoute à sa propre conversation locale (state.history)
    - annonce à voix haute via flutter_tts (TTS local, découplé du pipeline agent)
    - mémorise le message comme "en attente de réponse"

Utilisateur dit "Wafo" (pipeline Wake Word existant, inchangé)
    → "dis que je suis occupé" capturé comme commande
    → VoiceChatNotifier.stopListening() attache le contexte WhatsApp en
      attente à `end_of_speech` (§ CONTEXTE, séparation stricte — voir plus bas)
    ↓ WebSocket (backend, inchangé)
Agent W4FO (LangGraph) — voit le contexte WhatsApp injecté dans son prompt système
    → décide d'appeler l'outil whatsapp_reply("Je suis occupé aujourd'hui.")
    ↓
ActionRegistry (backend) valide → client_action {action: WHATSAPP_REPLY, payload: {text: ...}}
    ↓ WebSocket (canal client_action existant, réutilisé tel quel)
VoiceChatNotifier._handleClientAction → WhatsAppNotifier.sendReply(text)
    ↓ MethodChannel natif
WafoNotificationListenerService.sendReply()
    → déclenche l'action "Répondre" ORIGINALE de la notification WhatsApp
      (RemoteInput.addResultsToIntent + PendingIntent.send)
    → WhatsApp envoie le message, EXACTEMENT comme si l'utilisateur avait
      tapé sa réponse depuis la notification système.
```

**Aucun serveur Meta, aucune bibliothèque non officielle, aucun numéro
dédié.** Deux API Android publiques et documentées : `NotificationListenerService`
(lecture) et l'action "Répondre" `RemoteInput` déjà fournie par WhatsApp lui-même
dans ses notifications (envoi) — le même mécanisme qu'utilisent Android Auto,
Wear OS et les suggestions de réponse rapide de Google.

## § SÉPARATION DES CONTEXTES (demandée explicitement)

| Contexte | Où il vit | Portée |
|---|---|---|
| Conversation Flutter (voix) | `VoiceChatState.messages` | Persistant pendant la session WS |
| Conversation WhatsApp | `WhatsAppState.history` | Local, séparé, jamais mélangé au précédent |
| Message WhatsApp "en attente" | `WhatsAppState.pendingMessage` | **Transitoire** : un seul message, effacé après réponse |
| Mémoire utilisateur | Backend (`memory_repository`) | Inchangée, non touchée par WhatsApp |
| Tâches / Agenda | Backend (`task_repository`/`calendar_repository`) | Inchangés, non touchés par WhatsApp |

Le seul pont entre "conversation WhatsApp" et "agent W4FO" est
`AgentState["whatsapp_context"]` (backend) : un dict `{sender, text}`
injecté dans le prompt système **pour un seul tour**, jamais persisté dans
`conversation_history`, jamais mélangé à la mémoire permanente.

## Ce qui fonctionne réellement (sans nécessiter de compte/clé Meta)

- Lecture des notifications WhatsApp (texte + expéditeur), avec annonce
  vocale locale (`flutter_tts`).
- Réponse envoyée via le mécanisme officiel `RemoteInput` de la notification,
  déclenchée par une commande vocale passant par l'agent (function calling
  Mistral, comme les autres outils Task/Calendar).
- Séparation stricte des contextes (ci-dessus).
- Vérifié par des tests unitaires backend (`whatsapp_tools.py` : validation,
  troncature, erreurs structurées) et par relecture statique complète côté
  Kotlin/Dart (pas de toolchain Flutter/Android dans cet environnement pour
  compiler réellement — voir limitations plus bas).

## § LIMITES ASSUMÉES — à ne jamais présenter comme "100% fonctionnel"

1. **Nécessite l'app ouverte (premier plan).** L'`EventChannel` n'est
   branché que sur le moteur Flutter de `MainActivity` (le seul à exécuter
   l'arbre de providers Riverpod) — voir la doc dans
   `WafoNotificationListenerService.registerEventChannel`. Un message reçu
   pendant que l'app est totalement fermée ou en arrière-plan (même avec le
   service d'écoute Wake Word actif) ne sera lu/traité qu'au retour au
   premier plan. Couvrir le cas "app fermée" nécessiterait un pipeline de
   consommation complet dans le moteur headless existant (un
   `ProviderContainer`, un appel WebSocket agent, et `flutter_tts` exécutés
   sans UI) — non construit dans cette livraison, mais une extension
   naturelle du même mécanisme.
2. **Une seule conversation "en attente" à la fois.** Si Paul ET Julie
   écrivent coup sur coup, seul le dernier message reste "répondable" — le
   précédent reste visible dans l'historique mais n'est plus lié à une
   action "Répondre" active.
3. **Pas de solution de repli `AccessibilityService`.** Si une notification
   WhatsApp n'a pas d'action "Répondre" (rare : certains messages système,
   notification déjà consommée par l'utilisateur), W4FO peut la lire à voix
   haute mais ne peut pas y répondre. Documenté dans le code
   (`onNotificationPosted`, cas `canReply = false`).
4. **Risque ToS non nul, assumé explicitement par l'utilisateur.** WhatsApp
   interdit dans ses conditions d'utilisation l'automatisation de l'app par
   des moyens non officiels. L'usage ici (API Android publiques, usage
   personnel unique, pas d'envoi en masse) correspond à une catégorie
   d'applications tolérée en pratique depuis des années (ex. "Auto Reply for
   WhatsApp" sur le Play Store), mais aucune garantie absolue de non-bannissement
   ne peut être donnée.
5. **Fragilité potentielle.** Si WhatsApp change la structure de ses
   notifications (peu probable pour l'action "Répondre", mécanisme standard
   Android stable depuis des années, mais pas impossible), la lecture ou la
   réponse peut cesser de fonctionner sans préavis.
6. **Non testé sur appareil réel** dans cet environnement (pas de toolchain
   Flutter/Android/Kotlin disponible ici). Vérifié par : compilation Python
   du backend, tests unitaires du tool `whatsapp_reply` et du parsing du
   contexte WhatsApp, équilibrage syntaxique strict et relecture manuelle
   exhaustive de tout le code Kotlin/Dart. **Un test sur un téléphone Android
   réel, avec WhatsApp installé, reste indispensable avant mise en production.**

## Aucun credential à configurer

Cette architecture n'utilise AUCUNE clé, token, ou identifiant Meta —
puisqu'elle ne parle à aucun serveur Meta. Rien à ajouter dans `.env`, aucun
secret à gérer côté backend pour cette fonctionnalité. Seule action requise
côté utilisateur : accorder l'accès aux notifications à W4FO via l'écran
système (Réglages W4FO → WhatsApp → "Autoriser l'accès aux notifications"),
qui ouvre `Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS` — jamais accordé
silencieusement.
