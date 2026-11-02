import os

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import Select


class MySeleniumTests(StaticLiveServerTestCase):
    """Tasques del professor, realitzades al panell Django amb Selenium."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Única creació directa amb l'ORM autoritzada per l'enunciat.
        user = User.objects.create_user(
            "isard", "isard@isardvdi.com", "pirineus"
        )
        user.is_superuser = True
        user.is_staff = True
        user.save()

        opts = Options()
        if os.environ.get("CI") == "true" or os.environ.get("HEADLESS") == "1":
            opts.add_argument("-headless")
        if os.environ.get("FIREFOX_BIN"):
            opts.binary_location = os.environ["FIREFOX_BIN"]

        cls.selenium = webdriver.Firefox(options=opts)
        cls.selenium.implicitly_wait(5)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.selenium.quit()
        finally:
            super().tearDownClass()

    def entrar(self, usuari, contrasenya):
        self.selenium.get(f"{self.live_server_url}/admin/login/")
        self.selenium.find_element(By.ID, "id_username").send_keys(usuari)
        self.selenium.find_element(By.ID, "id_password").send_keys(contrasenya)
        self.selenium.find_element(
            By.CSS_SELECTOR, 'input[type="submit"]'
        ).click()
        self.assertIn(usuari.lower(), self.selenium.find_element(By.ID, "user-tools").text.lower())

    def test_grups_permisos_i_usuari_boss(self):
        self.entrar("isard", "pirineus")

        # 1. Crear basic, sense concedir-li cap permís.
        self.selenium.get(f"{self.live_server_url}/admin/auth/group/add/")
        self.selenium.find_element(By.ID, "id_name").send_keys("basic")
        self.assertEqual(
            len(self.selenium.find_element(By.ID, "id_permissions_to")
                .find_elements(By.TAG_NAME, "option")),
            0,
        )
        self.selenium.find_element(By.NAME, "_save").click()

        # 2. Crear admin amb els 8 permisos de User i Group.
        self.selenium.get(f"{self.live_server_url}/admin/auth/group/add/")
        self.selenium.find_element(By.ID, "id_name").send_keys("admin")
        disponibles = self.selenium.find_element(By.ID, "id_permissions_from")
        noms_permisos = []
        for opcio in disponibles.find_elements(By.TAG_NAME, "option"):
            # Etiquetes Django: «App | model | Can add/change/delete/view ...».
            parts = [p.strip().lower() for p in opcio.text.split("|")]
            if len(parts) == 3 and parts[1] in {"user", "group"}:
                noms_permisos.append(opcio.text)

        self.assertEqual(
            len(noms_permisos), 8,
            f"S'esperaven 8 permisos de User/Group: {noms_permisos}",
        )
        for nom in noms_permisos:
            Select(self.selenium.find_element(By.ID, "id_permissions_from"))\
                .select_by_visible_text(nom)
            self.selenium.find_element(By.ID, "id_permissions_add").click()

        seleccionats = self.selenium.find_element(By.ID, "id_permissions_to")
        permisos_assignats = [op.text for op in seleccionats.find_elements(By.TAG_NAME, "option")]
        self.assertCountEqual(permisos_assignats, noms_permisos)
        self.selenium.find_element(By.NAME, "_save").click()

        # 3. Comprovar per la interfície que basic continua sense permisos.
        self.selenium.get(f"{self.live_server_url}/admin/auth/group/")
        self.selenium.find_element(By.LINK_TEXT, "basic").click()
        self.assertEqual(
            len(self.selenium.find_element(By.ID, "id_permissions_to")
                .find_elements(By.TAG_NAME, "option")),
            0,
        )

        # 4. Crear boss mitjançant el formulari d'usuari del panell.
        contrasenya_boss = "BossPass2026!"
        self.selenium.get(f"{self.live_server_url}/admin/auth/user/add/")
        self.selenium.find_element(By.ID, "id_username").send_keys("boss")
        self.selenium.find_element(By.ID, "id_password1").send_keys(contrasenya_boss)
        self.selenium.find_element(By.ID, "id_password2").send_keys(contrasenya_boss)
        self.selenium.find_element(By.NAME, "_continue").click()

        # En editar boss es pot marcar is_staff i assignar-li admin.
        self.assertIn("/change/", self.selenium.current_url)
        staff = self.selenium.find_element(By.ID, "id_is_staff")
        if not staff.is_selected():
            staff.click()
        self.assertFalse(self.selenium.find_element(By.ID, "id_is_superuser").is_selected())
        Select(self.selenium.find_element(By.ID, "id_groups_from"))\
            .select_by_visible_text("admin")
        self.selenium.find_element(By.ID, "id_groups_add").click()
        self.assertEqual(
            [op.text for op in self.selenium.find_element(By.ID, "id_groups_to")
                .find_elements(By.TAG_NAME, "option")],
            ["admin"],
        )
        self.selenium.find_element(By.NAME, "_save").click()

        # 5. Tancar la sessió d'isard i entrar com a boss.
        self.selenium.find_element(
            By.CSS_SELECTOR, "#logout-form button[type='submit']"
        ).click()
        self.entrar("boss", contrasenya_boss)

        # 6. Comprovar les dues seccions i la possibilitat d'entrar-hi.
        self.selenium.get(f"{self.live_server_url}/admin/")
        self.assertTrue(self.selenium.find_elements(
            By.CSS_SELECTOR, '#content-main a[href$="/auth/user/"]'
        ), "boss no pot veure Users")
        self.assertTrue(self.selenium.find_elements(
            By.CSS_SELECTOR, '#content-main a[href$="/auth/group/"]'
        ), "boss no pot veure Groups")
        # Comprovació negativa: boss no té permisos sobre Questions.
        self.assertFalse(self.selenium.find_elements(
            By.CSS_SELECTOR, '#content-main a[href$="/polls/question/"]'
        ), "boss no hauria de veure Questions")

        self.selenium.find_element(
            By.CSS_SELECTOR, '#content-main a[href$="/auth/user/"]'
        ).click()
        self.assertTrue(self.selenium.find_elements(By.ID, "changelist"))

        self.selenium.get(f"{self.live_server_url}/admin/")
        self.selenium.find_element(
            By.CSS_SELECTOR, '#content-main a[href$="/auth/group/"]'
        ).click()
        self.assertTrue(self.selenium.find_elements(By.ID, "changelist"))
