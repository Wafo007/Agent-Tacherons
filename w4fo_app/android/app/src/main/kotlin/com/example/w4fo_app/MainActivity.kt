package com.example.w4fo_app

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.annotation.NonNull
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Pont natif <-> Flutter (`MethodChannel "w4fo/background_listening"`) pour
 * le contrôle du Foreground Service d'écoute vocale persistante
 * (`WafoBackgroundService`) — § ANDROID SERVICE / "communication avec Flutter".
 *
 * Responsabilités :
 * - démarrer/arrêter le service depuis Flutter (bouton dans les réglages) ;
 * - vérifier/demander la permission `POST_NOTIFICATIONS` (obligatoire côté
 *   service pour afficher sa notification persistante sur Android 13+) ;
 * - vérifier l'état de l'exemption d'optimisation de batterie, et ouvrir
 *   l'écran système correspondant (jamais d'octroi automatique/silencieux) ;
 * - relayer à Flutter le signal "l'app vient d'être ramenée au premier plan
 *   suite à une détection du mot-clé en arrière-plan" (`onWakeWordLaunch`),
 *   pour que `VoiceChatNotifier` démarre directement la capture de commande.
 */
class MainActivity : FlutterActivity() {

    companion object {
        const val EXTRA_WAKE_WORD_LAUNCH = "wake_word_launch"
        private const val CHANNEL = "w4fo/background_listening"
        private const val NOTIFICATION_PERMISSION_REQUEST_CODE = 4201
    }

    private var methodChannel: MethodChannel? = null
    private var whatsAppMethodChannel: MethodChannel? = null

    override fun configureFlutterEngine(@NonNull flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        val channel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
        channel.setMethodCallHandler { call, result ->
            when (call.method) {
                "startBackgroundListening" -> {
                    val intent = Intent(this, WafoBackgroundService::class.java)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        startForegroundService(intent)
                    } else {
                        startService(intent)
                    }
                    result.success(null)
                }
                "stopBackgroundListening" -> {
                    val intent = Intent(this, WafoBackgroundService::class.java).apply {
                        action = WafoBackgroundService.ACTION_STOP
                    }
                    startService(intent)
                    result.success(null)
                }
                "hasNotificationPermission" -> result.success(hasNotificationPermission())
                "requestNotificationPermission" -> {
                    requestNotificationPermission()
                    result.success(null)
                }
                "isIgnoringBatteryOptimizations" -> result.success(isIgnoringBatteryOptimizations())
                "requestIgnoreBatteryOptimizations" -> {
                    openBatteryOptimizationSettings()
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
        methodChannel = channel

        // § WHATSAPP (lecture + réponse on-device) : pont de contrôle séparé,
        // volontairement distinct du canal ci-dessus (domaines fonctionnels
        // différents — voir `WafoNotificationListenerService.kt`).
        val whatsAppChannel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, WafoNotificationListenerService.METHOD_CHANNEL)
        whatsAppChannel.setMethodCallHandler { call, result ->
            when (call.method) {
                "hasNotificationAccess" -> result.success(hasNotificationListenerAccess())
                "openNotificationAccessSettings" -> {
                    startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                    result.success(null)
                }
                "setListeningEnabled" -> {
                    WafoNotificationListenerService.listeningEnabled = call.argument<Boolean>("enabled") ?: false
                    if (!WafoNotificationListenerService.listeningEnabled) {
                        WafoNotificationListenerService.clearPending()
                    }
                    result.success(null)
                }
                "hasPendingMessage" -> result.success(WafoNotificationListenerService.hasPendingMessage())
                "sendReply" -> {
                    val text = call.argument<String>("text")
                    if (text.isNullOrBlank()) {
                        result.success(false)
                    } else {
                        result.success(WafoNotificationListenerService.sendReply(text))
                    }
                }
                "clearPendingMessage" -> {
                    WafoNotificationListenerService.clearPending()
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
        whatsAppMethodChannel = whatsAppChannel

        // § WHATSAPP : branche le canal d'événements sur CE moteur (premier
        // plan) — voir la doc de `WafoNotificationListenerService.registerEventChannel`
        // pour la justification (c'est ici, et seulement ici, que vit
        // l'arbre de widgets/providers Riverpod capable de traiter l'événement).
        WafoNotificationListenerService.registerEventChannel(flutterEngine.dartExecutor.binaryMessenger)

        // Si cette Activity est (re)créée suite au lancement déclenché par le
        // service d'arrière-plan (mot-clé détecté), on le signale à Flutter
        // dès que le moteur est prêt à recevoir des appels de méthode.
        maybeNotifyWakeWordLaunch(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        maybeNotifyWakeWordLaunch(intent)
    }

    private fun maybeNotifyWakeWordLaunch(intent: Intent?) {
        if (intent?.getBooleanExtra(EXTRA_WAKE_WORD_LAUNCH, false) == true) {
            intent.removeExtra(EXTRA_WAKE_WORD_LAUNCH)
            methodChannel?.invokeMethod("onWakeWordLaunch", null)
        }
    }

    private fun hasNotificationPermission(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
        return ContextCompat.checkSelfPermission(
            this, Manifest.permission.POST_NOTIFICATIONS
        ) == PackageManager.PERMISSION_GRANTED
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        ActivityCompat.requestPermissions(
            this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), NOTIFICATION_PERMISSION_REQUEST_CODE
        )
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == NOTIFICATION_PERMISSION_REQUEST_CODE) {
            methodChannel?.invokeMethod("onNotificationPermissionResult", hasNotificationPermission())
        }
    }

    private fun isIgnoringBatteryOptimizations(): Boolean {
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        return powerManager.isIgnoringBatteryOptimizations(packageName)
    }

    /**
     * Vérifie si l'utilisateur a accordé l'accès aux notifications à W4FO
     * (§ WHATSAPP). Cette permission ne s'accorde JAMAIS silencieusement :
     * elle passe obligatoirement par l'écran système ouvert via
     * `openNotificationAccessSettings` ci-dessus, que l'utilisateur doit
     * valider explicitement.
     */
    private fun hasNotificationListenerAccess(): Boolean {
        val enabledListeners = Settings.Secure.getString(contentResolver, "enabled_notification_listeners")
            ?: return false
        return enabledListeners.contains(packageName)
    }

    private fun openBatteryOptimizationSettings() {
        // Ouvre l'écran système standard listant les apps et leur statut
        // d'optimisation de batterie, plutôt que de déclencher directement la
        // boîte de dialogue "Ignorer l'optimisation" (action `REQUEST_IGNORE_
        // BATTERY_OPTIMIZATIONS`, nécessitant une permission dédiée et
        // fortement scrutée par les stores) : l'utilisateur choisit
        // explicitement, dans un écran Android natif, rien n'est accordé
        // automatiquement.
        startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
    }
}
