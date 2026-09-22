FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN ls -l /app
RUN cat /app/requirements.txt

RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "dashboard.py", "--server.address=0.0.0.0"]