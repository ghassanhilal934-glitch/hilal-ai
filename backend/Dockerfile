FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PORT=7860

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir bcrypt \
 && pip install --no-cache-dir --no-deps \
      gradio_client==2.7.2 \
      huggingface_hub==0.24.7 \
      httpx==0.28.1 \
      httpcore>=1.0 \
      h11>=0.16 \
      anyio>=4.0 \
      sniffio>=1.3 \
      fsspec>=2024.1 \
      requests>=2.31 \
      tqdm>=4.66 \
      pyyaml>=6.0 \
      click>=8.1 \
      filelock>=3.13 \
      packaging>=23 \
      websocket-client>=1.7 \
      websockets>=12

COPY . .
RUN mkdir -p outputs

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}"]
