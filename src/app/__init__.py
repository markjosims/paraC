from flask import Flask


def create_app():
    app = Flask(__name__, template_folder='../../static')

    # from src.app.routes import home, inflector, parser, corpus, config
    from src.app.routes import home, config
    app.register_blueprint(home.bp)
    # app.register_blueprint(inflector.bp, url_prefix='/inflector')
    # app.register_blueprint(parser.bp, url_prefix='/parser')
    # app.register_blueprint(corpus.bp, url_prefix='/corpus')
    app.register_blueprint(config.bp, url_prefix='/config')

    return app
