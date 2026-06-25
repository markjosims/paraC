# FeatureDefinitions
This config defines feature categories and enumerates possible values.
```yaml
kind: FeatureDefinitions
features:
    person: [1sg, 2sg, 3sg, 1pl, 2pl, 3pl]
    tense: [present, past, future]
    mood: [indicative, imperative, subjunctive]
```
A single `FeatureDefinitions` config may be used for an entire project, or features may be divided across multiple configs for readability and organization (e.g. by part of speech).
Keep in mind that the application will load all feature sets into a single list, so if the same feature name is defined in multiple locations it will raise an error.
Furthermore, there is no hierarchy or grouping of features by filename within the application.
Each part of speech, then, must declare its own feature set explicitly, see the [part of speech](config/parts_of_speech/README.md) documentation for more information.