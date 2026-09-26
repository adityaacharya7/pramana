FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
# The NER model is fetched at build time so the running demo needs no network.
RUN pip install --no-cache-dir -r /app/backend/requirements.txt \
    && python -m spacy download en_core_web_sm
COPY backend/pramana /app/backend/pramana
COPY dataset/tri_city_v1 /app/dataset/tri_city_v1
WORKDIR /app/backend
ENV PRAMANA_DATA_DIR=/data
EXPOSE 8000
# PRAMANA_BUILD (standard | demo) is set by docker-compose.
CMD ["sh", "-c", "python -m pramana.cli serve --host 0.0.0.0 --port 8000 $( [ \"$PRAMANA_BUILD\" = demo ] && echo --demo )"]
