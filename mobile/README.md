# DressMe mobile (Flutter)

Created with the folders below; run `flutter create . --org tn.esprit.dressme --project-name dressme`
**once** (M6) to generate android/ and ios/, then commit.

```
lib/
  main.dart
  app/        router, theme
  core/       api client, shared widgets, constants
  models/     Dart classes mirroring backend/shared/schemas
  features/<feature>/{data,logic,ui}
```

Rule: you only edit `lib/features/<your feature>/`. Changes to `core/`, `app/`, `models/` go through a PR.
