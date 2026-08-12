# Dossier windows/

Placeholder, comme `android/README.md`. Générer la structure native Windows via :

```bash
flutter create --platforms=windows .
```

Note : la capture micro (`record`) et la lecture audio (`just_audio`) ont un support
Windows variable selon les versions des plugins — vérifier leur compatibilité
Windows avant de lancer le portage (§13 du document d'architecture backend :
"tester très tôt un build Windows minimal pour détecter les plugins non
compatibles, notamment audio").
