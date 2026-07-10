from app import create_app, db

app = create_app()

if __name__ == "__main__":
    # For local development only — safe to keep
    with app.app_context():
        db.create_all()

    # Production (Render) automatically binds to 0.0.0.0:$PORT
    # Render sets PORT environment variable automatically
    import os
    port = int(os.environ.get("PORT", 5000))
    
    app.run(host="0.0.0.0", port=port)
