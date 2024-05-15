FROM python:3.9.8

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y build-essential postgresql-server-dev-all \
    && pip install psycopg2-binary

COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD gunicorn main:app -b 0.0.0.0:5000