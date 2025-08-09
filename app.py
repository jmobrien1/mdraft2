import os
import logging
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from sqlalchemy import text

from models import db


def create_app() -> Flask:
    """Flask application factory for mdraft 2.0."""
    load_dotenv()  # Load environment from .env for local dev

    app = Flask(__name__)

    # Basic configuration
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db_user = os.getenv("DB_USER", "")
    db_password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "")
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = os.getenv("DB_PORT", "5432")

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )

    # Initialize extensions
    db.init_app(app)

    # Ensure pgvector extension exists at startup (safe if already created)
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception as exc:
            app.logger.warning("Could not ensure pgvector extension exists: %s", exc)

    # CORS for future Next.js frontend
    cors_origin = os.getenv("CORS_ORIGIN", "http://localhost:3000")
    CORS(app, resources={r"/api/*": {"origins": cors_origin}})

    # Logging
    logging.basicConfig(level=logging.INFO)

    # Register routes
    from routes import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    # CLI: flask --app app.py init-db
    @app.cli.command("init-db")
    def init_db_command() -> None:  # pragma: no cover - CLI utility
        from click import echo

        with app.app_context():
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                db.create_all()
                echo("Initialized the database and ensured pgvector extension.")
            except Exception as exc:  # pragma: no cover
                echo(f"Failed to initialize DB: {exc}")

    return app


if __name__ == "__main__":
    # Local development server
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)


