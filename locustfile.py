from locust import HttpUser, task


class QuickstartUser(HttpUser):
    @task
    def stats_1(self):
        self.client.get("stats/1")

    @task
    def stats_2(self):
        self.client.get("stats/2")
