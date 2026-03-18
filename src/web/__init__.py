from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.config["SECRET_KEY"] = "dev"

    from src.web.routes import bp

    app.register_blueprint(bp)
    return app
