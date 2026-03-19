FROM python:3.10.12-bookworm

WORKDIR /opt/app

COPY c4_dashboard/requirements.txt /opt/app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY c4_dashboard /opt/app

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"]
