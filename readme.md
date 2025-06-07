## Teletram bot for ARM64 using OPENAI API LLM & qdrant vector database
Note that this is a USER BOT! not the (GODFATHER) GROUP BOT! 
This service is runnable in ARM64 arch type only! configuration is required to run it in other shape.

## Setting up (READ & DO THIS BEFORE MOVING ON)
- Go to telegram and create a user bot account. Obtain your TELEGRAM_API_ID and TELEGRAM_API_HASH. (google if you dont know how)
- Setup your own LLM and qdrant vector database endpoint
- Ensure you have the embbedding model download to the folder `EMB_MODEL`
- login for the first time locally to obtain the userbot_session.session file before being able to build the docker image

## Running locally
- create your vitual Env (for windows and wsl)
`python -m venv venv`

- Activate the env (windows CMD)
`venv\Scripts\activate`

- Activate the env (wsl)
`source venv/Scripts/activate`

- Run the code with:
```
python ./main.py # running the script
```

## Building image for ARM64
ensure your docker have ARM64 build else run:
Register QEMU `docker run --rm --privileged multiarch/qemu-user-static --reset -p yes` 
```
docker buildx rm multiarch-builder
docker buildx create --name multiarch-builder --driver docker-container --use
docker buildx inspect --bootstrap
```

run the following command to build to docker image:
`docker buildx build --no-cache --platform linux/arm64 -t arm64-telegram-bot:latest --load .`


## Transporting image

Save the docker image:
```
docker save arm64-telegram-bot:latest -o arm64-telegram-bot.tar
```

Transfer with the following command:
```
scp -i ./ssh-key-2025-06-02.key -r "C:\Project\work\auto-response\arm64-telegram-bot.tar" ubuntu@123.22.123.123:~/docker_compose/
```

On your ubuntu 22.04 load the image:
```
docker load -i arm64-telegram-bot.tar
```

Alternatively, you may use the docker hub to push your image to.

## Running on ARM64 VM

Ensure you have bring over the image and docker yml file.
Ensure that you have configure the docker-compose-telebot.yml file 

Run
```
docker compose -f docker-compose-telegrambot.yml up -d
```


## NOTE!

You will need to insert your own qdrant data to the database.
run `docker builder prune --all` if you have issue building

## Steps for Full start up

### Step 1. Serving a LLM
1. Download Ollama docker image and transfer it to your VM
2. Download a copy of the docker-compose.yml file for ollama (you can use the one below)
3. exec into your vm to pull the model or point your volume to a external folder

### Step 2. Serving qdrant
1. Download qdrant docker image and transfer it to your VM
2. Download a copy of the docker-compose.yml file for qdrant (you can use the one below)
4. 

### Step 2. Serving qdrant
1. Configure `docker-compose-telebot.yml`
2. Download the a embedding model and point your model folder. You can use the `download_EmbModel.py` file to pull the model to the emb_model
3. inset data to the vector database using `data_insertion.py`
   
### sample docker-compsoe.yml for ollama and qdrant
```
version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest # Use the official image directly, no custom build for Ollama
    container_name: ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      # Mount the transferred model directory directly
      - ./ollama_models/models:/root/.ollama/models
      # If Ollama creates other data (like history or logs) in /root/.ollama,
      # you might want a named volume for /root/.ollama/data or similar,
      # but for just models, this direct mount is good.
    environment:
      # Explicitly set OLLAMA_MODELS to ensure it uses the mounted path.
      # While the volume mount usually handles this, it's good practice.
      - OLLAMA_MODELS=/root/.ollama/models
    
  qdrant-vector-database:
    container_name: qdrant-vector-database
    image: qdrant/qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./qdrant_storage:/qdrant/storage:z

```


# CONTRIBUTED BY NG PING KEE