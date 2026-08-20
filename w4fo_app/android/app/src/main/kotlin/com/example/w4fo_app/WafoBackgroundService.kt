package com.example.w4fo_app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.embedding.engine.FlutterEngineCache
import io.flutter.embedding.engine.dart.DartExecutor
import io.flutter.embedding.engine.loader.FlutterLoader
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugins.GeneratedPluginRegistrant

/**
 * Foreground Service Android permettant à W4FO d'écouter le mot-clé de
 * réveil ("Wafo") lorsque l'application n'est PAS au premier plan.
 *
 * ## Ce que ce service fait RÉELLEMENT
 *
 * 1. Démarre en Foreground Service (type `microphone`), avec la notification
 *    persistante OBLIGATOIRE par le système (§ ANDROID SERVICE du brief :
 *    "notification obligatoire" — elle ne peut pas être masquée, c'est une
 *    contrainte Android, pas un choix de design).
 * 2. Démarre un second moteur Flutter, dit "headless" (sans aucune UI),
 *    exécutant UNIQUEMENT l'entrypoint Dart `backgroundWakeWordMain` (voir
 *    `lib/core/voice/background_wakeword_entrypoint.dart`) — qui lance
 *    l'écoute passive locale du mot-clé, exactement comme le fait l'écran
 *    vocal au premier plan, mais sans dépendre de cet écran.
 * 3. Dès que ce moteur headless signale la détection du mot-clé (via
 *    `MethodChannel`), ramène `MainActivity` au premier plan avec un extra
 *    `EXTRA_WAKE_WORD_LAUNCH` : c'est Flutter (côté UI, une fois relancé)
 *    qui enchaîne alors sur la capture de commande réelle, l'appel à
 *    l'orchestrateur d'agents et la synthèse vocale — pipeline existant,
 *    inchangé.
 *
 * ## Ce que ce service NE fait PAS (limites Android réelles, assumées)
 *
 * - Il ne garantit PAS de survivre indéfiniment : `START_STICKY` demande à
 *   Android de le relancer après un kill mémoire système, mais ceci n'est
 *   jamais garanti (Doze, App Standby, gestionnaires de batterie
 *   constructeur type Huawei/Xiaomi/Samsung peuvent l'empêcher).
 * - Il ne survit PAS à un "Forcer l'arrêt" explicite de l'app par
 *   l'utilisateur, ni à un swipe du multitâche récent sur de nombreux
 *   appareils (comportement standard Android — non contournable, et W4FO ne
 *   doit jamais prétendre le contourner).
 * - Le comportement du micro écran verrouillé dépend fortement du
 *   fabricant/de la version d'Android : ce service utilise les API standard
 *   documentées, sans aucune API privée ni contournement.
 * - L'exécution de `speech_to_text` (donc de la reconnaissance vocale
 *   elle-même) DANS ce moteur headless, sans Activity associée, n'est pas
 *   officiellement garantie par ce plugin : cela doit être validé sur un
 *   appareil réel (voir `background_wakeword_entrypoint.dart` et le README).
 *   Si cela ne fonctionne pas sur un modèle donné, le service reste
 *   fonctionnel (notification, cycle de vie) mais aucune détection n'aura
 *   lieu tant que l'app n'est pas revenue au premier plan — dégradation
 *   silencieuse et sans crash, jamais un blocage.
 */
class WafoBackgroundService : Service() {

    companion object {
        const val CHANNEL_ID = "wafo_background_listening"
        const val NOTIFICATION_ID = 4242
        const val ENGINE_CACHE_ID = "wafo_background_engine"
        const val DART_CHANNEL = "w4fo/background_wakeword"
        const val ACTION_STOP = "com.example.w4fo_app.action.STOP_BACKGROUND_LISTENING"
    }

    private var flutterEngine: FlutterEngine? = null
    private var methodChannel: MethodChannel? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        val notification = buildNotification(listening = true)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
        startHeadlessEngine()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        // Demande à Android de relancer ce service après un kill système —
        // sans garantie (voir limites documentées ci-dessus).
        return START_STICKY
    }

    private fun startHeadlessEngine() {
        val loader = FlutterLoader()
        loader.startInitialization(applicationContext)
        loader.ensureInitializationComplete(applicationContext, null)

        val engine = FlutterEngine(this)
        val entrypoint = DartExecutor.DartEntrypoint(loader.findAppBundlePath(), "backgroundWakeWordMain")
        engine.dartExecutor.executeDartEntrypoint(entrypoint)
        GeneratedPluginRegistrant.registerWith(engine)
        FlutterEngineCache.getInstance().put(ENGINE_CACHE_ID, engine)

        val channel = MethodChannel(engine.dartExecutor.binaryMessenger, DART_CHANNEL)
        channel.setMethodCallHandler { call, result ->
            when (call.method) {
                "wakeWordDetected" -> {
                    onWakeWordDetected()
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }

        flutterEngine = engine
        methodChannel = channel
    }

    private fun onWakeWordDetected() {
        updateNotification(listening = false)
        val launchIntent = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
            putExtra(MainActivity.EXTRA_WAKE_WORD_LAUNCH, true)
        }
        startActivity(launchIntent)
    }

    private fun buildNotification(listening: Boolean): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            if (manager.getNotificationChannel(CHANNEL_ID) == null) {
                val channel = NotificationChannel(
                    CHANNEL_ID,
                    "Écoute vocale W4FO",
                    // IMPORTANCE_LOW : notification visible mais silencieuse (pas de
                    // son/vibration à chaque mise à jour) — cohérent avec une
                    // notification persistante informative, pas une alerte.
                    NotificationManager.IMPORTANCE_LOW,
                )
                channel.description = "Indique que W4FO écoute le mot-clé « Wafo » en arrière-plan."
                manager.createNotificationChannel(channel)
            }
        }

        val stopIntent = Intent(this, WafoBackgroundService::class.java).apply { action = ACTION_STOP }
        val stopPendingIntent = PendingIntent.getService(
            this, 0, stopIntent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val contentIntent = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CHANNEL_ID)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }

        return builder
            .setContentTitle("W4FO")
            .setContentText(
                if (listening) "En écoute du mot-clé « Wafo »…" else "Commande en cours de traitement…"
            )
            // NOTE : icône de repli générique (icône de lancement de l'app).
            // Une icône monochrome dédiée aux notifications (recommandation
            // Android) pourra être ajoutée ultérieurement par le design.
            .setSmallIcon(applicationInfo.icon)
            .setOngoing(true)
            .setContentIntent(contentIntent)
            .addAction(0, "Désactiver", stopPendingIntent)
            .build()
    }

    private fun updateNotification(listening: Boolean) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, buildNotification(listening))
    }

    override fun onDestroy() {
        methodChannel?.invokeMethod("stop", null)
        methodChannel = null
        flutterEngine?.destroy()
        flutterEngine = null
        FlutterEngineCache.getInstance().remove(ENGINE_CACHE_ID)
        super.onDestroy()
    }
}
