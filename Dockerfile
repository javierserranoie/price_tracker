FROM python:3.8-slim

WORKDIR /opt/project
COPY . /opt/project

RUN pip install -r requirements.txt

CMD ["python", "pricetracker.py"]