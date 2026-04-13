from extensions import app
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.participants import participants_bp
from routes.api import api_bp

# ==========================================================
# REGISTER BLUEPRINTS
# ==========================================================

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(participants_bp)
app.register_blueprint(api_bp)

# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    app.run(debug=True)