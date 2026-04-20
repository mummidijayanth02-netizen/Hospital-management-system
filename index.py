from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    # In development we disable the reloader for predictability with custom ENV vars
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode, use_reloader=False, port=5001)
