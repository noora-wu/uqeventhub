# UQ Event Hub

A campus event site for discovering talks, socials, sport, and host organisations at the University of Queensland.

The live UQ deployment used Django with a MySQL database on a UQ server. That database is no longer available, so this repository publishes two parts:

- The site root is a static preview of the public pages, using the sample events stored in the original project. Sign-in, registration, and the host dashboard are not connected to a server.
- `server/` is the Django application, switched to SQLite so it can be run locally without the UQ database.

## Website

https://noora-wu.github.io/uqeventhub/

## Run the Django app locally

From `server/`:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/uqeventhub/`.

AI copy suggestions need an `OPENAI_API_KEY` in a `.env` file next to `manage.py`. Google and GitHub sign-in need their own client id and secret in the same file. The static preview does not use those credentials.
