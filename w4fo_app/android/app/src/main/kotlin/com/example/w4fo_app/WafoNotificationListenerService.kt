package com.example.w4fo_app

import android.app.Notification
import android.app.RemoteInput
import android.content.Intent
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import io.flutter.plugin.common.EventChannel

/**
 * Lit les notifications de messages WhatsApp reçues sur l'appareil, et
 * conserve la référence nécessaire pour y répondre directement, via l'action
 * "Répondre" intégrée par WhatsApp lui-même à sa notification (mécanisme
 * `RemoteInput`, API Android officielle utilisée par Android Auto, Wear OS,
 * et les suggestions de réponse rapide de Google).
 *
 * ## Ce que fait CE service
 *
 * - Écoute les notifications des paquets `com.whatsapp` (WhatsApp) et
 *   `com.whatsapp.w4b` (WhatsApp Business).
 * - Pour chaque notification de MESSAGE (ignorées : notifications de groupe
 *   "résumé", d'appel manqué, de statut...), extrait l'expéditeur et le
 *   texte, et les transmet à Flutter via un `EventChannel`.
 * - Mémorise, pour la DERNIÈRE notification pertinente, l'action "Répondre"
 *   (son `RemoteInput` + son `PendingIntent`) — c'est ce qui permet
 *   d'envoyer une réponse EXACTEMENT comme si l'utilisateur avait tapé sa
 *   réponse directement depuis la notification système.
 *
 * ## Ce que ce service NE fait PAS
 *
 * - Il n'ouvre JAMAIS l'application WhatsApp, ne lit ni ne modifie son
 *   interface, ne simule aucun tap sur l'écran (pas d'`AccessibilityService`
 *   dans cette implémentation — voir le README pour les cas non couverts).
 * - Il ne se connecte à AUCUN serveur Meta/WhatsApp : tout se passe en local,
 *   sur l'appareil, via les API publiques Android (`NotificationListenerService`,
 *   `RemoteInput`).
 * - Il ne conserve qu'UNE SEULE conversation "en attente de réponse" à la
 *   fois (la plus récente) — voir § LIMITES dans le README pour la
 *   justification de ce choix MVP.
 *
 * ## Activation
 *
 * Ce service ne démarre QUE si l'utilisateur a explicitement accordé l'accès
 * aux notifications à W4FO (écran système `ACTION_NOTIFICATION_LISTENER_SETTINGS`,
 * ouvert depuis les Réglages de l'app — voir `MainActivity.kt` et
 * `w4fo_app/lib/core/whatsapp/whatsapp_controller.dart`). Ce n'est PAS une
 * permission accordée silencieusement au moment de l'installation.
 */
class WafoNotificationListenerService : NotificationListenerService() {

    companion object {
        const val EVENT_CHANNEL = "w4fo/whatsapp_events"
        const val METHOD_CHANNEL = "w4fo/whatsapp_control"

        private const val PACKAGE_WHATSAPP = "com.whatsapp"
        private const val PACKAGE_WHATSAPP_BUSINESS = "com.whatsapp.w4b"
        private val WHATSAPP_PACKAGES = setOf(PACKAGE_WHATSAPP, PACKAGE_WHATSAPP_BUSINESS)

        // Référence globale statique : `NotificationListenerService` et
        // `MainActivity`/le MethodChannel de contrôle ne partagent pas
        // naturellement d'instance (cycles de vie Android indépendants). On
        // expose donc l'instance active courante pour que `sendReply()` (appelé
        // depuis le MethodChannel, voir plus bas) puisse l'atteindre. Pattern
        // standard pour ce type de service Android.
        @Volatile
        private var activeInstance: WafoNotificationListenerService? = null

        /** true si Flutter a explicitement demandé à surveiller WhatsApp. */
        @Volatile
        var listeningEnabled: Boolean = false

        fun sendReply(text: String): Boolean = activeInstance?.replyToPending(text) ?: false

        fun hasPendingMessage(): Boolean = activeInstance?.pending != null

        fun clearPending() {
            activeInstance?.pending = null
        }

        @Volatile
        private var eventSink: EventChannel.EventSink? = null

        /**
         * Branche l'`EventChannel` sur le moteur Flutter du PREMIER PLAN
         * (`MainActivity`), la SEULE instance qui exécute réellement l'arbre de
         * widgets/providers Riverpod de l'app (`WhatsAppNotifier` y vit).
         *
         * Volontairement PAS branché sur le moteur headless d'arrière-plan
         * (`WafoBackgroundService`, utilisé pour le Wake Word) : celui-ci
         * n'exécute que `backgroundWakeWordMain()`, sans `ProviderScope` ni
         * arbre de widgets — un événement WhatsApp qui y arriverait n'aurait
         * personne pour le traiter utilement. § LIMITE assumée et documentée
         * dans le README : la lecture/réponse WhatsApp nécessite donc que
         * l'app soit ouverte (premier plan) au moment de la réception —
         * contrairement au Wake Word, qui fonctionne lui en arrière-plan.
         * Couvrir aussi le cas "app fermée" nécessiterait un pipeline de
         * consommation complet dans le moteur headless (ProviderContainer,
         * appel WS agent, TTS) — non construit dans cette livraison.
         */
        fun registerEventChannel(messenger: io.flutter.plugin.common.BinaryMessenger) {
            EventChannel(messenger, EVENT_CHANNEL).setStreamHandler(
                object : EventChannel.StreamHandler {
                    override fun onListen(arguments: Any?, sink: EventChannel.EventSink?) {
                        eventSink = sink
                    }

                    override fun onCancel(arguments: Any?) {
                        eventSink = null
                    }
                }
            )
        }
    }

    /** Une notification de message WhatsApp en attente de réponse. */
    private data class PendingWhatsAppMessage(
        val sender: String,
        val text: String,
        val notificationKey: String,
        val replyPendingIntent: android.app.PendingIntent,
        // L'objet RemoteInput ORIGINAL fourni par la notification WhatsApp
        // (pas une reconstruction) : il peut porter des options spécifiques
        // (type de contenu accepté, choix suggérés...) qu'il faut préserver
        // pour que WhatsApp accepte la réponse programmatique.
        val remoteInput: RemoteInput,
    )

    private var pending: PendingWhatsAppMessage? = null

    override fun onListenerConnected() {
        super.onListenerConnected()
        activeInstance = this
    }

    override fun onListenerDisconnected() {
        activeInstance = null
        super.onListenerDisconnected()
    }

    override fun onDestroy() {
        activeInstance = null
        super.onDestroy()
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (!listeningEnabled) return
        if (sbn.packageName !in WHATSAPP_PACKAGES) return

        val notification = sbn.notification
        val extras = notification.extras

        // Ignore les notifications "résumé de groupe" (une seule notification
        // agrégée quand plusieurs messages arrivent d'un coup — sans texte de
        // message exploitable individuellement) et les notifications sans texte
        // (appels manqués, changements de statut...).
        if ((notification.flags and Notification.FLAG_GROUP_SUMMARY) != 0) return

        val sender = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString()?.trim()
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()?.trim()
        if (sender.isNullOrEmpty() || text.isNullOrEmpty()) return

        val replyAction = notification.actions?.firstOrNull { action ->
            action.remoteInputs?.isNotEmpty() == true
        }
        val remoteInput = replyAction?.remoteInputs?.firstOrNull()

        if (replyAction == null || remoteInput == null) {
            // Pas d'action "Répondre" sur cette notification (rare : message
            // système, ou notification déjà consommée) — on transmet quand
            // même la lecture à Flutter, mais la réponse ne sera pas possible
            // tant qu'un nouveau message avec action de réponse n'arrive pas.
            // Voir § LIMITES du README pour la solution de repli envisagée
            // (AccessibilityService), non implémentée dans cette version.
            eventSink?.success(
                mapOf("sender" to sender, "text" to text, "canReply" to false)
            )
            return
        }

        pending = PendingWhatsAppMessage(
            sender = sender,
            text = text,
            notificationKey = sbn.key,
            replyPendingIntent = replyAction.actionIntent,
            remoteInput = remoteInput,
        )

        eventSink?.success(mapOf("sender" to sender, "text" to text, "canReply" to true))
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        // Si la notification en attente est fermée (l'utilisateur l'a lue ou
        // balayée directement dans WhatsApp), on invalide la réponse en
        // attente : répondre à une notification fermée n'est plus fiable.
        if (pending?.notificationKey == sbn.key) {
            pending = null
        }
    }

    /**
     * Envoie [text] comme réponse au message WhatsApp actuellement en
     * attente, en déclenchant PROGRAMMATIQUEMENT l'action "Répondre" fournie
     * par la notification WhatsApp elle-même — EXACTEMENT le mécanisme
     * qu'utilise Android quand l'utilisateur tape une réponse directement
     * depuis la zone de notification. Retourne `false` si aucun message
     * n'est en attente ou si l'envoi échoue.
     */
    private fun replyToPending(text: String): Boolean {
        val message = pending ?: return false
        return try {
            val resultIntent = Intent()
            val bundle = android.os.Bundle()
            bundle.putCharSequence(message.remoteInput.resultKey, text)
            RemoteInput.addResultsToIntent(arrayOf(message.remoteInput), resultIntent, bundle)
            message.replyPendingIntent.send(applicationContext, 0, resultIntent)
            pending = null
            true
        } catch (_: Exception) {
            false
        }
    }
}
