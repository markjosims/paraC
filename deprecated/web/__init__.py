from flask import Flask

from src.editors.configs import normalize_config_dir


def create_app(config_dir: str | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="../../static", static_url_path="/static")
    app.config["SECRET_KEY"] = "dev"
    validated = _validated_config_dir(config_dir)
    app.config["CONFIG_DIR"] = validated

    from src.editors.routes import bp, GRAMMAR_REGISTRY_CACHE

    app.register_blueprint(bp)

    if validated:
        from src.editors.watcher import start_watcher

        app.config["WATCHER"] = start_watcher(validated, GRAMMAR_REGISTRY_CACHE)

    return app


def _validated_config_dir(config_dir: str | None) -> str | None:
    if config_dir is None:
        return None

    normalized = normalize_config_dir(config_dir)
    if normalized is None:
        raise ValueError(f"Directory not found: {config_dir}")
    return str(normalized)
