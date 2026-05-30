from app.Http.Controllers.HomeController import HomeController
from larajango.routing import router

router.get("/", HomeController.index, name="home")
