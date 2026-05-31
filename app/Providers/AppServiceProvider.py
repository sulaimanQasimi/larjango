from larajango.foundation import ServiceProvider


class AppServiceProvider(ServiceProvider):
    def register(self):
        pass

    def boot(self):
        from app.Models.User import User
        from app.Policies.UserPolicy import UserPolicy
        from larajango.authorization import Gate

        Gate.policy(User, UserPolicy)
