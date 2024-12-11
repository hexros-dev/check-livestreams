import os
from dotenv import load_dotenv
load_dotenv()

def create_cookies_file():
  cookies_content = os.getenv("COOKIES_CONTENT")
  if cookies_content:
    with open("cookies.txt", "w") as file:
      file.write(cookies_content)
  else:
    raise ValueError("Cookies content not found in environment variables.")

if __name__ == "__main__":
  create_cookies_file()
