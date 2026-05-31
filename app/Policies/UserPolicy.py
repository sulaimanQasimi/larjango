class UserPolicy:
    def view(self, user, model):
        return user.is_authenticated and (user.pk == model.pk or user.can("view_user"))

    def create(self, user):
        return user.is_authenticated and user.can("add_user")

    def update(self, user, model):
        return user.is_authenticated and (user.pk == model.pk or user.can("change_user"))

    def delete(self, user, model):
        return user.is_authenticated and user.can("delete_user") and user.pk != model.pk
