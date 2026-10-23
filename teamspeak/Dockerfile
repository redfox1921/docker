FROM python:3.12-slim
RUN pip install --no-cache-dir paramiko==3.4.0
COPY afk_mover.py /app/afk_mover.py
CMD ["python", "-u", "/app/afk_mover.py"]
