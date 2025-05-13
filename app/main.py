from elasticapm.contrib.starlette import ElasticAPM, make_apm_client
from fastapi import FastAPI
from nicegui import ui
from typing import Callable
import asyncio
import functools
import httpx as r
#import psutil
import asyncpg

DATABASE_URL = "postgresql://webapp_user:webapp_password@postgres:5432/webapp_db"
#DATABASE_URL = "postgresql://webapp_user:password@localhost:5432/webapp_db"

try:
  apm = make_apm_client({
      'SERVICE_NAME': 'webapp',
      'SECRET_TOKEN': 'supersecrettoken',
      # SERVER_URL must be set to "fleet-server" if running as a docker container.
      # if running as a local python script, then set the url to "LOCALHOST"
      'SERVER_URL': 'http://fleet:8200',
      'ENVIRONMENT': 'development'
  })
except Exception as e:
  print('failed to create client')

app = FastAPI()

try:
  app.add_middleware(ElasticAPM, client=apm)
except Exception as e:
  print('failed to add APM Middleware')


@app.get("/custom_message/{message}")
async def custom_message(message: str):
    apm.capture_message(f"Custom Message: {message}")
    return {"message": f"Custom Message:  {message}"}


@app.get("/error")
async def throw_error():
    try:
        1 / 0
    except Exception as e:
        apm.capture_exception()
    return {"message": "Failed Successfully :)"}


@app.on_event("startup")
async def startup_event():
    global db_pool
    db_pool = await connect_to_db()

def init(fastapi_app: FastAPI) -> None:
    global db_messages_area  # Make it accessible across functions
    @ui.page('/', title="APM Demo App")
    async def show():
        with ui.header(elevated=True).style('background-color: #3874c8').classes('items-center justify-between'):
            ui.markdown('### APM DEMO')
            ui.button(on_click=lambda: right_drawer.toggle(), icon='menu').props('flat color=white')

        with ui.right_drawer(fixed=False).style('background-color: #ebf1fa').props('bordered') as right_drawer:
            ui.chat_message('Hello Elastic Stack User!', name='APM Robot', stamp='now',
                            avatar='https://robohash.org/apm_robot')
            ui.chat_message('Now you can store and retrieve messages in PostgreSQL.', name='APM Robot',
                            stamp='now', avatar='https://robohash.org/apm_robot')

        with ui.footer().style('background-color: #3874c8'):
            ui.label('APM DEMO PAGE')

        with ui.card():
            ui.label('Generate Error - Python')
            ui.button('Generate', on_click=python_error)

        with ui.card():
            ui.label('Generate Custom Message')
            custom_message_text = ui.input(placeholder='Message')
            ui.button('Generate').on('click', handler=lambda: gen_custom_message(custom_message_text.value))

        with ui.card():
            ui.label('Interact with Database')
            message_input = ui.input(placeholder="Enter a message")
            ui.button("Insert into DB").on("click", handler=lambda: insert_message_ui(message_input.value))
            ui.button("Query Messages").on("click", handler=lambda: query_messages_ui(db_messages_area))
            db_messages_area = ui.markdown("**Stored Messages:**")  # Placeholder for messages

    ui.run_with(fastapi_app, storage_secret='supersecret')

async def insert_message_ui(message):
    await insert_data(db_pool, message)
    ui.notify("Message inserted!")

async def query_messages_ui(db_messages_area):
    ui.notify("Fetching messages... Please wait.")
    
    messages = await query_data(db_pool)
    print(f"Fetched messages: {messages}")  # Debugging output

    if not messages:
        ui.notify("No messages found!")
        db_messages_area.set_content("**No messages in database**")
        return

    # Extract text from query results
    message_list = "\n".join([f"- {record['text']}" for record in messages])

    ui.notify("Messages fetched successfully!")

    # Ensure UI updates dynamically
    db_messages_area.set_content(f"**Stored Messages:**\n{message_list}")
    db_messages_area.update()  # Explicitly request UI update
        
async def io_bound(callback: Callable, *args: any, **kwargs: any):
    '''Makes a blocking function awaitable; pass function as first parameter and its arguments as the rest'''
    return await asyncio.get_event_loop().run_in_executor(None, functools.partial(callback, *args, **kwargs))


async def connect_to_db():
    return await asyncpg.create_pool(DATABASE_URL)

async def insert_data(pool, message: str):
    try:
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO messages (text) VALUES ($1)", message)
    except Exception as e:
        print(f"Database Insert Error: {e}")
        apm.capture_exception()

async def query_data(pool):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM messages")
        
async def python_error():
    try:
        res = await io_bound(r.get, 'http://localhost:8000/error')
        ui.notify(res.text)
    except Exception as e:
        apm.capture_exception()
        ui.notify(f'{e}')

async def setup_db():
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                text TEXT NOT NULL
            )
        """)
    return pool

async def js_error():
    try:
        res = await ui.run_javascript('fetch("http://localhost:8000/error")')
        ui.notify(f'Message: Failed Successfully :)')
    except Exception as e:
        apm.capture_exception()
        ui.notify(f'{e}')


async def gen_custom_message(text_message):
    try:
        res = await io_bound(r.get, 'http://localhost:8000/custom_message/' + str(text_message))
        ui.notify(res.text)
    except Exception as e:
        apm.capture_exception()
        ui.notify(f'{e}')

init(app)

try:
  apm.capture_message('App Loaded, Hello World!')
except Exception as e:
  print('error: ' + e)

if __name__ == '__main__':
    print('Please start the app with the "uvicorn" command as shown in the start.sh script')