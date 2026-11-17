FROM python:3.12-slim

# INSTALL_ML=false donne une image légère (embeddings "hashing" uniquement), utile en CI
ARG INSTALL_ML=true
ARG EMBEDDING_MODEL=intfloat/multilingual-e5-small

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/models

COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir -r requirements-ml.txt; fi

# Télécharge le modèle d'embeddings au build : l'API démarre ensuite sans accès réseau
RUN if [ "$INSTALL_ML" = "true" ]; then \
      python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"; \
    fi

# Modèle déjà dans l'image : pas d'appel réseau à Hugging Face au démarrage
ENV HF_HUB_OFFLINE=1

COPY . .
RUN useradd --create-home app && mkdir -p /data/storage && chown -R app /app /data
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
