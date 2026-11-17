.PHONY: up down demo eval test logs

up:            ## Lance la stack (db + api + web)
	docker compose up -d --build

down:
	docker compose down

demo:          ## Importe le corpus de démonstration fictif
	docker compose exec api python -m scripts.seed_demo /data/corpus/demo

eval:          ## Évalue le pipeline sur eval/questions.jsonl
	docker compose exec api python -m scripts.evaluate

test:          ## Tests (nécessite la base : docker compose up -d db)
	docker compose exec db psql -U aerodocs -tc "SELECT 1 FROM pg_database WHERE datname='aerodocs_test'" | grep -q 1 || \
	  docker compose exec db createdb -U aerodocs aerodocs_test
	cd backend && TEST_DATABASE_URL=postgresql+psycopg://aerodocs:aerodocs@localhost:5432/aerodocs_test python -m pytest -q

logs:
	docker compose logs -f api
