import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'wafo_wake_word_detector.dart';

const _channelName = 'w4fo/background_wakeword';

/// Entrypoint Dart exécuté par le Foreground Service Android
/// (`WafoBackgroundService.kt`) dans un moteur Flutter **headless** (sans
/// aucune UI), lorsque l'app n'est pas au premier plan.
///
/// Doit rester un top-level function annoté `@pragma('vm:entry-point')` :
/// c'est ce qui permet à Flutter de le conserver lors du tree-shaking AOT et
/// à `DartExecutor` (côté Kotlin) de le retrouver par son nom.
///
/// ## Ce que cette fonction fait
///
/// Instancie [WafoWakeWordDetector] (le même détecteur, 100% local, utilisé
/// par l'écran vocal au premier plan) et le démarre en boucle : dès que le
/// mot-clé est détecté, elle le signale au service natif via `MethodChannel`
/// (charge ensuite à `WafoBackgroundService.onWakeWordDetected` de ramener
/// `MainActivity` au premier plan), puis relance l'écoute après une courte
/// pause.
///
/// ## ⚠️ Limite majeure, À VALIDER SUR APPAREIL RÉEL
///
/// Le plugin `speech_to_text` est conçu et testé pour un usage depuis une
/// `Activity` Flutter au premier plan. Son fonctionnement correct dans un
/// moteur headless (Service seul, sans Activity) N'EST PAS garanti par sa
/// documentation officielle. Deux issues possibles à l'exécution réelle :
///
/// - ça fonctionne : la détection du mot-clé a lieu réellement en
///   arrière-plan, tant que le process du service est vivant ;
/// - ça échoue silencieusement (le moteur `SpeechRecognizer` natif refuse de
///   démarrer sans Activity liée) : dans ce cas, [WafoWakeWordDetector.start]
///   ne lèvera pas nécessairement d'exception bruyante, mais aucun mot-clé ne
///   sera jamais détecté tant que l'app n'est pas revenue au premier plan.
///   Le Foreground Service continuera néanmoins de tourner normalement
///   (notification, cycle de vie) — dégradation silencieuse, jamais un crash.
///
/// Ce point doit être vérifié sur un ou plusieurs appareils Android réels
/// avant toute communication produit annonçant l'Always-On comme "terminé".
/// S'il s'avère non fiable selon les appareils, l'étape suivante logique est
/// de remplacer, dans ce fichier uniquement, l'appel à `speech_to_text` par
/// un appel direct à `android.speech.SpeechRecognizer` écrit en Kotlin
/// directement dans `WafoBackgroundService`, qui n'a pas cette contrainte
/// (un `Service` peut légitimement posséder son propre `SpeechRecognizer`).
///
/// ## Ce que cette fonction NE fait PAS
///
/// Aucune capture de commande, aucun appel à l'orchestrateur d'agents,
/// aucune synthèse vocale : ce moteur headless n'a accès à aucun des
/// providers Riverpod de l'app (pas de `ProviderContainer` ici), et ne doit
/// gérer QUE la détection du mot-clé. Le reste du pipeline continue de vivre
/// exclusivement dans le moteur Flutter principal (celui de `MainActivity`),
/// une fois l'app ramenée au premier plan.
@pragma('vm:entry-point')
void backgroundWakeWordMain() {
  WidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel(_channelName);
  WafoWakeWordDetector? detector;
  Timer? restartTimer;
  StreamSubscription<void>? detectionSubscription;
  var stopped = false;

  Future<void> stopAndCleanUp() async {
    stopped = true;
    restartTimer?.cancel();
    await detectionSubscription?.cancel();
    await detector?.dispose();
  }

  channel.setMethodCallHandler((call) async {
    if (call.method == 'stop') {
      await stopAndCleanUp();
    }
  });

  Future<void> startListeningLoop() async {
    if (stopped) return;

    final localDetector = WafoWakeWordDetector();
    detector = localDetector;

    detectionSubscription = localDetector.onWakeWordDetected.listen((_) async {
      await localDetector.stop();
      try {
        await channel.invokeMethod('wakeWordDetected');
      } on PlatformException {
        // Le service natif a peut-être déjà été arrêté entre-temps : ce
        // process headless n'a aucune UI pour remonter une erreur, on
        // l'ignore silencieusement plutôt que de le faire planter.
      }
      if (!stopped) {
        // Relance l'écoute après une courte pause, indépendamment de ce que
        // fait l'app une fois ramenée au premier plan (pas encore de
        // coordination fine entre les deux instances de détecteur — voir
        // limite documentée dans le README de core/voice/).
        restartTimer = Timer(const Duration(seconds: 8), () {
          unawaited(startListeningLoop());
        });
      }
    });

    try {
      await localDetector.start();
    } catch (_) {
      // Échec de démarrage (voir limite documentée ci-dessus) : on retente
      // après une pause plus longue plutôt que de boucler en erreur serrée.
      if (!stopped) {
        restartTimer = Timer(const Duration(seconds: 30), () {
          unawaited(startListeningLoop());
        });
      }
    }
  }

  unawaited(startListeningLoop());
}
