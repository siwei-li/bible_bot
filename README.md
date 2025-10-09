# Bible translation WhatsApp chatbot

Thanks to Joel Matthew's great [blog article](https://www.etenlab.org/post/bible-translation-and-whatsapp) at ETEN Labs, we decided to build WhatsApp bot to collect more data from speakers of low-resource languages.


## Implementation


```
# Local development
pip3 install -r requirements.txt
python3 -m uvicorn poc_app:fastapi_app --reload --port LOCAL_PORT

# Docker
docker compose up --build
```

## Future work
- It would be nice to 

---
text='hi', image=None, video=None, sticker=None, document=None, audio=None, caption=None, reaction=None, location=None, contacts=None
