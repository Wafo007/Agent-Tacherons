# Dossier android/

Ce dossier est un placeholder. Le projet natif Android complet (gradle, manifests,
icônes...) n'a pas pu être généré dans l'environnement ayant servi à créer ce
squelette (pas de SDK Flutter disponible pour exécuter `flutter create`).

Pour générer la structure native complète, exécuter à la racine du projet Flutter :

```bash
flutter create --platforms=android .
```

Cela ajoutera tous les fichiers nécessaires (build.gradle, AndroidManifest.xml,
dossiers res/, etc.) sans écraser le code déjà présent dans `lib/`.

N'oubliez pas d'ajouter les permissions requises dans `android/app/src/main/AndroidManifest.xml` :

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.INTERNET" />
```

(nécessaires pour la capture micro et les appels réseau vers le backend).
