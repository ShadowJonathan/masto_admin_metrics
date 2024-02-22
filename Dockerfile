FROM python:3.11

ADD requirements.txt .

RUN pip install -r requirements.txt

ADD main.py .

CMD ["python", "-u", "./main.py"]