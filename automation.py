"""
Automatisation des candidatures spontanées sur La Bonne Alternance (LBA).
Supporte PLUSIEURS candidats en parallèle, chacun avec son propre navigateur.
Pause automatique quand la limite est atteinte → reprise le lendemain à la même heure.
"""

import asyncio
import json
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

BASE_URL = "https://labonnealternance.apprentissage.beta.gouv.fr"

# ── Toutes les grandes villes de France ──────────────────────────────────────
CITIES_DEFAULT = [
    # Île-de-France
    {"name": "Paris",              "lat": 48.8566, "lon": 2.3522},
    {"name": "Boulogne-Billancourt","lat": 48.8397, "lon": 2.2399},
    {"name": "Nanterre",           "lat": 48.8924, "lon": 2.2071},
    {"name": "Créteil",            "lat": 48.7911, "lon": 2.4628},
    {"name": "Versailles",         "lat": 48.8014, "lon": 2.1301},
    {"name": "Évry-Courcouronnes", "lat": 48.6243, "lon": 2.4296},
    # Nord / Hauts-de-France
    {"name": "Lille",              "lat": 50.6292, "lon": 3.0573},
    {"name": "Roubaix",           "lat": 50.6942, "lon": 3.1746},
    {"name": "Tourcoing",         "lat": 50.7240, "lon": 3.1613},
    {"name": "Amiens",            "lat": 49.8941, "lon": 2.2958},
    {"name": "Dunkerque",         "lat": 51.0343, "lon": 2.3768},
    {"name": "Valenciennes",      "lat": 50.3570, "lon": 3.5235},
    {"name": "Calais",            "lat": 50.9513, "lon": 1.8587},
    {"name": "Beauvais",          "lat": 49.4295, "lon": 2.0807},
    {"name": "Compiègne",         "lat": 49.4178, "lon": 2.8260},
    {"name": "Laon",              "lat": 49.5639, "lon": 3.6244},
    # Grand Est
    {"name": "Strasbourg",        "lat": 48.5734, "lon": 7.7521},
    {"name": "Metz",              "lat": 49.1193, "lon": 6.1757},
    {"name": "Nancy",             "lat": 48.6921, "lon": 6.1844},
    {"name": "Reims",             "lat": 49.2583, "lon": 4.0317},
    {"name": "Mulhouse",          "lat": 47.7508, "lon": 7.3359},
    {"name": "Colmar",            "lat": 48.0794, "lon": 7.3558},
    {"name": "Troyes",            "lat": 48.2973, "lon": 4.0744},
    {"name": "Charleville-Mézières","lat": 49.7711, "lon": 4.7203},
    {"name": "Épinal",            "lat": 48.1726, "lon": 6.4510},
    {"name": "Châlons-en-Champagne","lat": 48.9566, "lon": 4.3631},
    # Auvergne-Rhône-Alpes
    {"name": "Lyon",              "lat": 45.7640, "lon": 4.8357},
    {"name": "Clermont-Ferrand",  "lat": 45.7772, "lon": 3.0870},
    {"name": "Grenoble",          "lat": 45.1885, "lon": 5.7245},
    {"name": "Saint-Étienne",     "lat": 45.4397, "lon": 4.3872},
    {"name": "Annecy",            "lat": 45.8992, "lon": 6.1294},
    {"name": "Valence",           "lat": 44.9334, "lon": 4.8924},
    {"name": "Chambéry",          "lat": 45.5646, "lon": 5.9178},
    {"name": "Villeurbanne",      "lat": 45.7715, "lon": 4.8800},
    {"name": "Bourg-en-Bresse",   "lat": 46.2056, "lon": 5.2255},
    {"name": "Aurillac",          "lat": 44.9261, "lon": 2.4418},
    {"name": "Le Puy-en-Velay",   "lat": 45.0435, "lon": 3.8853},
    {"name": "Moulins",           "lat": 46.5645, "lon": 3.3327},
    {"name": "Privas",            "lat": 44.7355, "lon": 4.5979},
    # Nouvelle-Aquitaine
    {"name": "Bordeaux",          "lat": 44.8378, "lon": -0.5792},
    {"name": "Limoges",           "lat": 45.8315, "lon": 1.2578},
    {"name": "Poitiers",          "lat": 46.5802, "lon": 0.3404},
    {"name": "La Rochelle",       "lat": 46.1603, "lon": -1.1511},
    {"name": "Pau",               "lat": 43.2951, "lon": -0.3708},
    {"name": "Bayonne",           "lat": 43.4929, "lon": -1.4748},
    {"name": "Angoulême",         "lat": 45.6486, "lon": 0.1560},
    {"name": "Niort",             "lat": 46.3234, "lon": -0.4593},
    {"name": "Périgueux",         "lat": 45.1849, "lon": 0.7218},
    {"name": "Agen",              "lat": 44.2033, "lon": 0.6166},
    {"name": "Brive-la-Gaillarde","lat": 45.1587, "lon": 1.5321},
    {"name": "Mont-de-Marsan",    "lat": 43.8945, "lon": -0.4991},
    {"name": "Guéret",            "lat": 46.1727, "lon": 1.8715},
    {"name": "Tulle",             "lat": 45.2666, "lon": 1.7701},
    # Occitanie
    {"name": "Toulouse",          "lat": 43.6047, "lon": 1.4442},
    {"name": "Montpellier",       "lat": 43.6108, "lon": 3.8767},
    {"name": "Nîmes",             "lat": 43.8367, "lon": 4.3601},
    {"name": "Perpignan",         "lat": 42.6986, "lon": 2.8954},
    {"name": "Béziers",           "lat": 43.3440, "lon": 3.2150},
    {"name": "Narbonne",          "lat": 43.1849, "lon": 3.0035},
    {"name": "Albi",              "lat": 43.9279, "lon": 2.1491},
    {"name": "Tarbes",            "lat": 43.2328, "lon": 0.0783},
    {"name": "Castres",           "lat": 43.6061, "lon": 2.2419},
    {"name": "Montauban",         "lat": 44.0176, "lon": 1.3548},
    {"name": "Rodez",             "lat": 44.3497, "lon": 2.5753},
    {"name": "Auch",              "lat": 43.6465, "lon": 0.5855},
    {"name": "Cahors",            "lat": 44.4491, "lon": 1.4366},
    {"name": "Carcassonne",       "lat": 43.2130, "lon": 2.3491},
    {"name": "Foix",              "lat": 42.9638, "lon": 1.6078},
    {"name": "Mende",             "lat": 44.5183, "lon": 3.4980},
    # Provence-Alpes-Côte d'Azur
    {"name": "Marseille",         "lat": 43.2965, "lon": 5.3698},
    {"name": "Nice",              "lat": 43.7102, "lon": 7.2620},
    {"name": "Toulon",            "lat": 43.1242, "lon": 5.9280},
    {"name": "Aix-en-Provence",   "lat": 43.5297, "lon": 5.4474},
    {"name": "Avignon",           "lat": 43.9493, "lon": 4.8055},
    {"name": "Cannes",            "lat": 43.5528, "lon": 7.0174},
    {"name": "Antibes",           "lat": 43.5804, "lon": 7.1251},
    {"name": "Gap",               "lat": 44.5594, "lon": 6.0786},
    {"name": "Digne-les-Bains",   "lat": 44.0932, "lon": 6.2357},
    # Bretagne
    {"name": "Rennes",            "lat": 48.1173, "lon": -1.6778},
    {"name": "Brest",             "lat": 48.3904, "lon": -4.4861},
    {"name": "Lorient",           "lat": 47.7483, "lon": -3.3666},
    {"name": "Vannes",            "lat": 47.6559, "lon": -2.7604},
    {"name": "Saint-Brieuc",      "lat": 48.5141, "lon": -2.7600},
    {"name": "Quimper",           "lat": 47.9960, "lon": -4.1024},
    {"name": "Saint-Malo",        "lat": 48.6493, "lon": -2.0076},
    # Pays de la Loire
    {"name": "Nantes",            "lat": 47.2184, "lon": -1.5536},
    {"name": "Angers",            "lat": 47.4784, "lon": -0.5632},
    {"name": "Le Mans",           "lat": 48.0061, "lon": 0.1996},
    {"name": "Saint-Nazaire",     "lat": 47.2736, "lon": -2.2137},
    {"name": "La Roche-sur-Yon",  "lat": 46.6703, "lon": -1.4268},
    {"name": "Laval",             "lat": 48.0733, "lon": -0.7729},
    # Normandie
    {"name": "Rouen",             "lat": 49.4432, "lon": 1.0999},
    {"name": "Caen",              "lat": 49.1829, "lon": -0.3707},
    {"name": "Le Havre",          "lat": 49.4944, "lon": 0.1079},
    {"name": "Cherbourg-en-Cotentin","lat": 49.6337, "lon": -1.6222},
    {"name": "Évreux",            "lat": 49.0241, "lon": 1.1508},
    {"name": "Dieppe",            "lat": 49.9223, "lon": 1.0780},
    {"name": "Alençon",           "lat": 48.4311, "lon": 0.0917},
    # Centre-Val de Loire
    {"name": "Tours",             "lat": 47.3941, "lon": 0.6848},
    {"name": "Orléans",           "lat": 47.9029, "lon": 1.9040},
    {"name": "Bourges",           "lat": 47.0810, "lon": 2.3988},
    {"name": "Blois",             "lat": 47.5861, "lon": 1.3359},
    {"name": "Chartres",          "lat": 48.4564, "lon": 1.4841},
    {"name": "Châteauroux",       "lat": 46.8103, "lon": 1.6913},
    # Bourgogne-Franche-Comté
    {"name": "Dijon",             "lat": 47.3220, "lon": 5.0415},
    {"name": "Besançon",          "lat": 47.2378, "lon": 6.0241},
    {"name": "Belfort",           "lat": 47.6380, "lon": 6.8628},
    {"name": "Auxerre",           "lat": 47.7979, "lon": 3.5714},
    {"name": "Chalon-sur-Saône",  "lat": 46.7833, "lon": 4.8536},
    {"name": "Nevers",            "lat": 46.9899, "lon": 3.1590},
    {"name": "Mâcon",             "lat": 46.3066, "lon": 4.8296},
    {"name": "Lons-le-Saunier",   "lat": 46.6747, "lon": 5.5507},
    {"name": "Vesoul",            "lat": 47.6209, "lon": 6.1547},
    # Corse
    {"name": "Ajaccio",           "lat": 41.9192, "lon": 8.7386},
    {"name": "Bastia",            "lat": 42.6975, "lon": 9.4510},
    # DOM-TOM
    {"name": "Fort-de-France",    "lat": 14.6161, "lon": -61.0588},
    {"name": "Pointe-à-Pitre",    "lat": 16.2411, "lon": -61.5331},
    {"name": "Saint-Denis (Réunion)","lat": -20.8823, "lon": 55.4504},
    {"name": "Cayenne",           "lat": 4.9372,  "lon": -52.3260},
]

JOB_SEARCHES_DEFAULT = [
    {
        "name": "Développement web, intégration",
        "romes": "M1805,M1855,M1825,M1834,M1861,E1210,E1405,M1865,M1877,M1886,M1887",
    },
]


def extract_cv_info(pdf_path: str) -> dict:
    """Extrait nom, prénom, email, téléphone depuis un CV PDF."""
    info = {"lastname": "", "firstname": "", "email": "", "phone": ""}
    path = Path(pdf_path)
    if not path.exists() or not path.suffix.lower() == ".pdf":
        return info
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            text = ""
            for page in pdf.pages[:3]:
                text += (page.extract_text() or "") + "\n"
    except Exception:
        return info

    # Email
    m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    if m:
        info["email"] = m.group(0)

    # Téléphone français
    m = re.search(r"(?:\+33[\s.]?|0)[1-9](?:[\s.\-]?\d{2}){4}", text)
    if m:
        info["phone"] = re.sub(r"[\s.\-]", "", m.group(0))

    # Nom / Prénom : première ligne avec 2-4 mots alphabétiques
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:5]:
        if re.match(r"^(curriculum|cv |résumé|profil|objectif|contact)", line, re.IGNORECASE):
            continue
        words = line.split()
        if 2 <= len(words) <= 4:
            alpha_words = [w for w in words if re.match(r"^[A-ZÀ-Üa-zà-ÿ\-]+$", w)]
            if len(alpha_words) >= 2:
                upper_words = [w for w in alpha_words if w == w.upper() and len(w) > 1]
                other_words = [w for w in alpha_words if w != w.upper()]
                if upper_words:
                    info["lastname"] = upper_words[0].capitalize()
                    if other_words:
                        info["firstname"] = other_words[0].capitalize()
                else:
                    info["firstname"] = alpha_words[0].capitalize()
                    info["lastname"] = alpha_words[1].capitalize()
                break

    return info


class LBAAutomation:
    """Automatise l'envoi de candidatures pour UN candidat."""

    def __init__(
        self,
        candidate_id: str,
        config: dict,
        stop_event: threading.Event,
        pause_event: threading.Event,
        callbacks: dict = None,
        resume_state: dict = None,
    ):
        self.candidate_id = candidate_id
        self.config = config
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.callbacks = callbacks or {}
        self.resume_state = resume_state or {}
        self.sent_file = Path("sent_applications.json")
        self.sent: list = self._load_sent()
        self.stats: dict = {
            "status": "running",
            "sent_today": 0,
            "skipped": 0,
            "errors": 0,
            "current_city": "",
            "current_job": "",
            "current_company": "",
            "paused_until": self.resume_state.get("paused_until"),
            "last_city_index": self.resume_state.get("last_city_index", 0),
            "last_job_index": self.resume_state.get("last_job_index", 0),
        }
        # Restaurer compteurs depuis l'état sauvegardé
        self.stats["skipped"] = self.resume_state.get("skipped", 0)
        self.stats["errors"] = self.resume_state.get("errors", 0)
        self._name = f"{config.get('firstname', '?')} {config.get('lastname', '?')}"

    # ------------------------------------------------------------------ helpers

    def _load_sent(self) -> list:
        if self.sent_file.exists():
            try:
                return json.loads(self.sent_file.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save_sent(self) -> None:
        self.sent_file.write_text(
            json.dumps(self.sent, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _already_sent(self, siret: str) -> bool:
        cid = self.candidate_id
        return any(
            s.get("siret") == siret and s.get("candidate_id") == cid
            for s in self.sent
        )

    def _record_sent(self, siret: str, company: str, city: str, job: str) -> None:
        self.sent.append({
            "candidate_id": self.candidate_id,
            "candidate_name": self._name,
            "siret": siret,
            "company": company,
            "city": city,
            "job": job,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
        })
        self._save_sent()

    def _log(self, message: str, level: str = "info") -> None:
        now = datetime.now().strftime("%H:%M:%S")
        tagged = f"[{self._name}] {message}"
        print(f"[{now}] [{level.upper()}] {tagged}")
        if cb := self.callbacks.get("log"):
            cb({
                "time": now,
                "message": tagged,
                "level": level,
                "candidate_id": self.candidate_id,
            })

    def _update_stats(self, **kwargs) -> None:
        self.stats.update(kwargs)
        if cb := self.callbacks.get("status"):
            cb(self.candidate_id, self.stats.copy())

    def _stopped(self) -> bool:
        return self.stop_event.is_set()

    # ------------------------------------------------------------------ main

    async def run(self) -> None:
        from playwright.async_api import async_playwright

        self._log("🚀 Démarrage de l'automatisation")
        headless = self.config.get("headless", False)
        delay = int(self.config.get("delay_between_applications", 3))

        cities = CITIES_DEFAULT
        jobs = self.config.get("job_searches", JOB_SEARCHES_DEFAULT)

        # Indices de reprise
        start_job_idx = self.stats.get("last_job_index", 0)
        start_city_idx = self.stats.get("last_city_index", 0)

        # Villes échouées à réessayer
        retry_queue: list[tuple[int, int, dict, dict]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            ctx = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )

            for job_idx, job in enumerate(jobs):
                if self._stopped():
                    break
                if job_idx < start_job_idx:
                    continue
                for city_idx, city in enumerate(cities):
                    if self._stopped():
                        break
                    # Reprendre là où on s'est arrêté
                    if job_idx == start_job_idx and city_idx < start_city_idx:
                        continue

                    # ── Vérifier si en pause ──
                    if self.pause_event.is_set():
                        resume_at = self.stats.get("paused_until")
                        if resume_at:
                            self._log(f"⏸️  En pause jusqu'à {resume_at}")
                            while self.pause_event.is_set() and not self._stopped():
                                await asyncio.sleep(30)
                                now = datetime.now()
                                try:
                                    target = datetime.fromisoformat(resume_at)
                                    if now >= target:
                                        self._log("▶️  Reprise automatique !")
                                        self.pause_event.clear()
                                        self._update_stats(
                                            status="running", paused_until=None
                                        )
                                        break
                                except Exception:
                                    pass
                            if self._stopped():
                                break

                    self._update_stats(
                        current_city=city["name"], current_job=job["name"],
                        last_city_index=city_idx, last_job_index=job_idx,
                    )
                    try:
                        search_page, entries = await self._search_companies(ctx, job, city)
                    except Exception as exc:
                        self._log(f"  ⚠️  Page lente, on reviendra : {city['name']} ({exc})", "warning")
                        retry_queue.append((job_idx, city_idx, job, city))
                        continue
                    try:
                        for siret, href in entries:
                            if self._stopped():
                                break
                            if self.pause_event.is_set():
                                break
                            if self._already_sent(siret):
                                self.stats["skipped"] += 1
                                self._log(f"⏭️  Déjà candidaté: {siret}")
                                continue
                            company_url = (
                                href if href.startswith("http") else f"{BASE_URL}{href}"
                            )
                            apply_page = await ctx.new_page()
                            try:
                                result = await self._apply_on_page(
                                    apply_page, siret, company_url,
                                    city["name"], job["name"],
                                )
                            finally:
                                await apply_page.close()
                            if result == "limit":
                                self._handle_rate_limit()
                                break
                            await asyncio.sleep(delay)
                    finally:
                        try:
                            await search_page.close()
                        except Exception:
                            pass

            # ── Réessayer les villes qui ont échoué ──
            if retry_queue and not self._stopped():
                self._log(f"🔄 Réessai de {len(retry_queue)} ville(s) échouée(s)")
                for job_idx, city_idx, job, city in retry_queue:
                    if self._stopped():
                        break
                    if self.pause_event.is_set():
                        break
                    self._log(f"🔄 Retry: {job['name']} → {city['name']}")
                    self._update_stats(
                        current_city=city["name"], current_job=job["name"],
                    )
                    try:
                        search_page, entries = await self._search_companies(ctx, job, city)
                    except Exception as exc:
                        self._log(f"  ❌ Retry échoué: {city['name']} ({exc})", "error")
                        self.stats["errors"] += 1
                        self._update_stats(errors=self.stats["errors"])
                        continue
                    try:
                        for siret, href in entries:
                            if self._stopped() or self.pause_event.is_set():
                                break
                            if self._already_sent(siret):
                                continue
                            company_url = (
                                href if href.startswith("http") else f"{BASE_URL}{href}"
                            )
                            apply_page = await ctx.new_page()
                            try:
                                result = await self._apply_on_page(
                                    apply_page, siret, company_url,
                                    city["name"], job["name"],
                                )
                            finally:
                                await apply_page.close()
                            if result == "limit":
                                self._handle_rate_limit()
                                break
                            await asyncio.sleep(delay)
                    finally:
                        try:
                            await search_page.close()
                        except Exception:
                            pass

            await browser.close()

        self._update_stats(status="stopped")
        self._log("✅ Automatisation terminée")

    def _handle_rate_limit(self):
        now = datetime.now()
        resume = now + timedelta(days=1)
        resume_str = resume.strftime("%Y-%m-%dT%H:%M:%S")
        self._log(
            f"🛑 LIMITE ATTEINTE — pause automatique jusqu'à {resume_str}",
            "warning",
        )
        self.stats["paused_until"] = resume_str
        self.pause_event.set()
        self._update_stats(status="paused", paused_until=resume_str)

    # ------------------------------------------------------------------ search

    async def _search_companies(self, ctx, job: dict, city: dict) -> list:
        from playwright.async_api import TimeoutError as PwTimeout

        self._log(f"🔍 {job['name']} → {city['name']}")
        page = await ctx.new_page()
        entries: list[tuple[str, str]] = []

        async def _check_only_emploi(pg):
            await asyncio.sleep(1)
            for sel in [
                "#displayedItemTypes-Formations",
                'input[name="Formations"]',
            ]:
                try:
                    el = await pg.query_selector(sel)
                    if el and await el.is_checked():
                        await pg.evaluate("(el) => el.click()", el)
                        self._log("  ☐  Formations décoché")
                        await asyncio.sleep(0.5)
                        break
                except Exception:
                    pass
            for sel in [
                "#displayedItemTypes-Emplois",
                'input[name="Emplois"]',
            ]:
                try:
                    el = await pg.query_selector(sel)
                    if el and not await el.is_checked():
                        await pg.evaluate("(el) => el.click()", el)
                        self._log("  ☑️  Emplois coché")
                        await asyncio.sleep(0.5)
                    break
                except Exception:
                    pass

        try:
            # ── Ouvrir la page d'accueil ──
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=90_000)
            await asyncio.sleep(5)
            await _check_only_emploi(page)

            # ── Métier ───────────────────────────────────────────────
            job_input = page.locator(
                "input#metier, "
                'input[placeholder*="métier"], '
                'input[placeholder*="formation"]'
            ).first

            if await job_input.count() > 0:
                await job_input.click()
                await job_input.fill("")
                search_term = " ".join(job["name"].split(",")[0].split()[:3])[:20]
                self._log(f"  ✏️  Métier : {search_term!r}")
                await job_input.type(search_term, delay=90)
                await asyncio.sleep(4)

                keywords = [w.lower() for w in job["name"].split() if len(w) > 3]
                matched = False
                for opt_sel in [
                    '[role="option"]',
                    '[role="listbox"] li',
                    'ul[role="listbox"] li',
                ]:
                    opts = page.locator(opt_sel)
                    count = await opts.count()
                    for i in range(count):
                        opt = opts.nth(i)
                        if not await opt.is_visible():
                            continue
                        txt = (await opt.inner_text()).strip().lower()
                        if any(kw in txt for kw in keywords):
                            await opt.click()
                            matched = True
                            self._log(f"  ✅  Option métier : {txt[:50]}")
                            await asyncio.sleep(0.6)
                            break
                    if matched:
                        break

                if not matched:
                    first_opt = page.locator('[role="option"]').first
                    if await first_opt.count() > 0 and await first_opt.is_visible():
                        txt = await first_opt.inner_text()
                        await first_opt.click()
                        self._log(f"  ☑️  Première option : {txt.strip()[:50]}")
                    else:
                        await job_input.press("Enter")
                    await asyncio.sleep(0.6)

            # ── Ville ────────────────────────────────────────────────
            city_input = None
            for sel in [
                "input#lieu",
                'input[placeholder*="commune"]',
                'input[placeholder*="département"]',
                'input[placeholder*="localisation"]',
                'input[aria-label*="lieu"]',
            ]:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    city_input = loc
                    break

            if city_input:
                await city_input.click()
                await city_input.fill("")
                self._log(f"  🏙️  Ville : {city['name']}")
                await city_input.type(city["name"][:8], delay=90)
                await asyncio.sleep(4)
                first_city = page.locator('[role="option"]').first
                if await first_city.count() > 0 and await first_city.is_visible():
                    txt = await first_city.inner_text()
                    await first_city.click()
                    self._log(f"  ✅  Ville sélectionnée : {txt.strip()[:40]}")
                else:
                    await city_input.press("Enter")
                await asyncio.sleep(0.6)

            # ── Rechercher ───────────────────────────────────────────
            search_btn = page.locator(
                'button:has-text("Rechercher"), button[type="submit"]'
            ).first
            async with page.expect_navigation(
                wait_until="domcontentloaded", timeout=90_000
            ):
                if await search_btn.count() > 0:
                    await search_btn.click()
                else:
                    await page.keyboard.press("Enter")

            self._log(f"  → Résultats : {page.url[:80]}")
            # Attendre le chargement - patients mais pas bloquants
            for wait_ms in [45_000, 30_000]:
                try:
                    await page.wait_for_load_state("networkidle", timeout=wait_ms)
                    break
                except PwTimeout:
                    pass
            await asyncio.sleep(4)
            await _check_only_emploi(page)
            await asyncio.sleep(1)

            # Attendre que le contenu soit réellement rendu (SPA React)
            for _ in range(20):
                body_len = await page.evaluate("() => document.body.innerText.length")
                if body_len > 3000:
                    break
                await asyncio.sleep(2)

            # Detect card selector — essayer plusieurs fois avec délai
            card_sel = None
            for attempt in range(5):
                for sel in [".fr-card", "[class*='card']", "li[data-testid]", "a[href*='recruteurs_lba']"]:
                    try:
                        await page.wait_for_selector(sel, timeout=15_000)
                        card_sel = sel
                        break
                    except PwTimeout:
                        continue
                if card_sel:
                    break
                # Pas trouvé, attendre un peu et réessayer
                await asyncio.sleep(4)

            if not card_sel:
                # Debug: log what's on the page
                debug_info = await page.evaluate(r"""() => {
                    const all = document.querySelectorAll('*');
                    const classes = new Set();
                    for (const el of all) {
                        for (const c of el.classList) {
                            if (c.toLowerCase().includes('card') || c.toLowerCase().includes('result')
                                || c.toLowerCase().includes('item') || c.toLowerCase().includes('entreprise'))
                                classes.add(el.tagName + '.' + c);
                        }
                    }
                    const links = document.querySelectorAll('a[href*="recruteurs"]');
                    return {
                        classes: [...classes].slice(0, 20),
                        recruteurLinks: links.length,
                        bodyLen: document.body.innerText.length
                    };
                }""")
                self._log(f"  🔍 Debug selectors: {debug_info}", "warning")
                self._log(f"  ⚠️  Aucune carte: {city['name']}", "warning")
                return page, []

            self._log(f"  ✅  Cartes détectées ({card_sel})")

            # ── Scroll + collecte incrémentale ───────────────────────
            JS_COLLECT = r"""
(cardSel) => {
    const results = [];
    const seen = new Set();
    const cards = Array.from(document.querySelectorAll(cardSel));
    cards.forEach(card => {
        const text = (card.textContent || '').toLowerCase();
        if (text.includes('vous avez d') && text.includes('postul')) return;
        const hasSimplifiee = text.includes('candidature simplifi');
        const hasSpontanee = !!card.querySelector('[aria-describedby*="candidature-spontanee-tag-"]')
                          || text.includes('candidature spontan');
        if (!hasSimplifiee) return;
        let a = card.querySelector('a[href*="recruteurs_lba"]');
        if (!a) a = card.querySelector('.fr-card__title a');
        if (!a) a = card.querySelector('h3 a');
        if (!a) a = card.querySelector('a[href*="/postuler"]');
        if (!a) a = card.querySelector('a');
        if (!a || !a.href) return;
        const href = a.href;
        let siret = '';
        let m = href.match(/recruteurs_lba\/(\d+)\//);
        if (m) { siret = m[1]; }
        else { m = href.match(/(\d{14})/); if (m) siret = m[1]; }
        if (!siret) return;
        if (seen.has(siret)) return;
        seen.add(siret);
        const type = hasSpontanee ? 'spontanee' : 'simplifiee';
        results.push({ siret, href, type });
    });
    return { total: cards.length, entries: results };
}
"""
            JS_SCROLL = r"""
() => {
    const step = Math.max(300, Math.floor(window.innerHeight * 0.88));
    for (const el of document.querySelectorAll('main, [role="main"], article, div')) {
        try {
            const st = getComputedStyle(el);
            if (!/auto|scroll|overlay/.test(st.overflowY || '')) continue;
            if (el.scrollHeight <= el.clientHeight + 80) continue;
            const t = el.scrollTop;
            el.scrollTop = Math.min(t + step, el.scrollHeight - el.clientHeight);
            if (el.scrollTop !== t) return;
        } catch (e) {}
    }
    window.scrollBy(0, step);
}
"""
            accumulated: dict[str, dict] = {}
            stagnation = 0
            prev_unique = 0

            self._log("  📜 Défilement + collecte…")
            while stagnation < 28:
                js_result = await page.evaluate(JS_COLLECT, card_sel)
                for item in js_result["entries"]:
                    s = item["siret"]
                    if s not in accumulated:
                        accumulated[s] = {"href": item["href"], "type": item["type"]}

                n = len(accumulated)
                if n > prev_unique:
                    self._log(f"  📜 {n} entreprise(s) trouvée(s)")
                    prev_unique = n
                    stagnation = 0
                else:
                    stagnation += 1

                for btn_text in ["Voir plus", "Charger plus", "Afficher plus"]:
                    try:
                        btn = page.locator(f'button:has-text("{btn_text}")').first
                        if await btn.count() > 0 and await btn.is_visible():
                            await btn.click()
                            await asyncio.sleep(2)
                            stagnation = 0
                    except Exception:
                        pass

                await page.evaluate(JS_SCROLL)
                try:
                    last_card = page.locator(card_sel).last
                    await last_card.scroll_into_view_if_needed(timeout=2500)
                except Exception:
                    pass
                await asyncio.sleep(0.75)

            for s, v in accumulated.items():
                entries.append((s, v["href"]))
                label = "SPONTANÉE" if v["type"] == "spontanee" else "SIMPLIFIÉE"
                self._log(f"  🏢 [{label}] SIRET {s}")

            self._log(f"  → {len(entries)} entreprise(s) « Candidature simplifiée »")
            await page.evaluate("window.scrollTo(0, 0)")

        except Exception as exc:
            self._log(f"  ❌ Recherche: {exc}", "error")
            self.stats["errors"] += 1

        return page, entries

    # ------------------------------------------------------------------ apply

    async def _apply_on_page(
        self, page, siret: str, url: str, city_name: str, job_name: str
    ):
        from playwright.async_api import TimeoutError as PwTimeout

        self._update_stats(current_company=siret)
        self._log(f"📝 SIRET: {siret}")
        company_name = siret
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            # Attendre que React hydrate (la page affiche un skeleton d'abord)
            for _ in range(30):
                body_len = await page.evaluate("() => document.body.innerText.length")
                if body_len > 2000:
                    break
                await asyncio.sleep(2)
            await asyncio.sleep(3)

            body_text = await page.inner_text("body")
            if "vous avez atteint" in body_text.lower():
                self._log("  🛑 LIMITE ATTEINTE", "warning")
                return "limit"

            for sel in [
                ".mui-gbrs06 > span:first-child",
                "[class*='gbrs06'] span",
                "h1",
            ]:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        txt = (await el.inner_text()).strip()
                        if txt:
                            company_name = txt
                            break
                except Exception:
                    pass

            self._log(f"  🏢 {company_name}")
            self._update_stats(current_company=company_name)

            # ── Trouver et cliquer le bouton "Postuler" (ouvre le modal) ──
            btn = None
            for btn_sel in [
                '[data-testid="candidature-not-sent"]',
                '[data-testid="postuler-button"]',
                'button:has-text("envoie ma candidature")',
                'button:has-text("candidature spontanée")',
                'button:has-text("Postuler")',
                'button:has-text("Candidature")',
                'a:has-text("candidature spontanée")',
                'a:has-text("Postuler")',
            ]:
                try:
                    loc = page.locator(btn_sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        btn = loc
                        break
                except Exception:
                    pass

            if not btn:
                self._log("  ⚠️  Bouton postuler introuvable", "warning")
                btn_debug = await page.evaluate(r"""
                    () => Array.from(document.querySelectorAll('button, a'))
                        .filter(b => b.offsetParent !== null)
                        .filter(b => /(postul|candid|spontan|envoie)/i.test(b.textContent))
                        .map(b => ({tag: b.tagName, text: b.textContent.trim().substring(0,50)}))
                        .slice(0, 5)
                """)
                self._log(f"  🔍 Boutons candidature: {btn_debug}", "warning")
                return

            # Scroll vers le bouton et clic
            await btn.scroll_into_view_if_needed()
            await asyncio.sleep(0.3)
            await btn.click()
            self._log("  🖱️  Bouton postuler cliqué → attente du formulaire")
            await asyncio.sleep(10)

            body_text2 = await page.inner_text("body")
            if "vous avez atteint" in body_text2.lower():
                self._log("  🛑 LIMITE ATTEINTE (après clic)", "warning")
                return "limit"

            ok = await self._fill_form(page, company_name)
            if ok:
                self._record_sent(siret, company_name, city_name, job_name)
                self.stats["sent_today"] += 1
                self._update_stats(sent_today=self.stats["sent_today"])
                self._log(f"  ✅ Candidature envoyée: {company_name}", "success")
            else:
                self.stats["errors"] += 1
                self._update_stats(errors=self.stats["errors"])
                self._log(f"  ⚠️  Échec: {company_name}", "warning")

        except Exception as exc:
            self.stats["errors"] += 1
            self._update_stats(errors=self.stats["errors"])
            self._log(f"  ❌ Erreur: {exc}", "error")

    async def _fill_form(self, page, company_name: str) -> bool:
        from playwright.async_api import TimeoutError as PwTimeout

        cfg = self.config

        try:
            # ── Attendre que le formulaire modal soit visible ──
            form_found = False
            for form_sel in [
                '[data-testid="CandidatureSpontaneeTitle"]',
                '[data-testid="candidature-form"]',
                'h1:has-text("Candidature spontanée")',
                'h2:has-text("Candidature spontanée")',
                'form',
                '[role="dialog"] form',
                '[role="dialog"]',
            ]:
                try:
                    await page.wait_for_selector(form_sel, timeout=20_000)
                    form_found = True
                    self._log("  📋 Formulaire détecté")
                    break
                except PwTimeout:
                    continue

            if not form_found:
                self._log("  ⏱️  Formulaire non visible", "warning")
                h_texts = await page.evaluate(r"""
                    () => Array.from(document.querySelectorAll('h1,h2,h3,h4'))
                        .filter(h => h.offsetParent !== null)
                        .map(h => h.textContent.trim().substring(0,60)).slice(0,8)
                """)
                self._log(f"  🔍 Titres visibles: {h_texts}", "warning")
                return False

            await asyncio.sleep(1)

            # ── Champs du formulaire (MUI inputs: click + selectAll + type) ──
            field_map = [
                ('input#lastName,  input[name="applicant_last_name"]', "lastname"),
                ('input#firstName, input[name="applicant_first_name"]', "firstname"),
                ('input#email,     input[name="applicant_email"]', "email"),
                ('input#phone,     input[name="applicant_phone"]', "phone"),
            ]
            for selector_group, key in field_map:
                value = cfg.get(key, "")
                if not value:
                    continue
                filled = False
                for sel in selector_group.split(","):
                    sel = sel.strip()
                    try:
                        field = await page.query_selector(sel)
                        if field:
                            await field.click()
                            await asyncio.sleep(0.2)
                            await page.keyboard.press("Control+a")
                            await page.keyboard.press("Backspace")
                            await field.type(value, delay=30)
                            await asyncio.sleep(0.3)
                            self._log(f"  ✏️  {key}: rempli")
                            filled = True
                            break
                    except Exception:
                        pass
                if not filled:
                    self._log(f"  ⚠️  Champ {key} introuvable", "warning")

            # ── Message ──
            template = cfg.get("message_template", "")
            if template:
                msg = (
                    template.replace("{company}", company_name)
                    .replace("{firstname}", cfg.get("firstname", ""))
                    .replace("{lastname}", cfg.get("lastname", ""))
                )
                for ta_sel in [
                    'textarea#message',
                    'textarea[data-testid="message"]',
                    'textarea[name="applicant_message"]',
                    'textarea',
                ]:
                    try:
                        ta = await page.query_selector(ta_sel)
                        if ta:
                            await ta.click()
                            await asyncio.sleep(0.2)
                            await page.keyboard.press("Control+a")
                            await page.keyboard.press("Backspace")
                            await ta.type(msg, delay=10)
                            self._log("  📝 Message rempli")
                            await asyncio.sleep(0.4)
                            break
                    except Exception:
                        pass

            # ── CV ──
            cv_path = cfg.get("cv_path", "")
            if cv_path and Path(cv_path).exists():
                fi = await page.query_selector('input[type="file"]')
                if fi:
                    await fi.set_input_files(cv_path)
                    self._log("  📄 CV chargé, attente upload…")
                    # Attendre que le CV soit bien uploadé
                    await asyncio.sleep(12)
                else:
                    self._log("  ⚠️  Input file introuvable", "warning")
            else:
                self._log("  ⚠️  CV non configuré ou introuvable", "warning")

            # ── Cocher toutes les checkboxes MUI ──
            # Les checkboxes LBA sont des MuiFormControlLabel avec input caché
            labels = await page.query_selector_all(
                ".MuiFormControlLabel-root"
            )
            for label in labels:
                try:
                    # Vérifier si la checkbox interne n'est pas déjà cochée
                    cb = await label.query_selector('input[type="checkbox"]')
                    if cb and not await cb.is_checked():
                        await label.click()
                        self._log("  ☑️  Checkbox cochée")
                        await asyncio.sleep(0.3)
                except Exception:
                    pass

            await asyncio.sleep(3)

            # ── Trouver le bouton submit DANS le formulaire ──
            # Le bouton submit a data-testid="candidature-not-sent" et type="submit"
            # C'est le MÊME testid que le postuler mais il est DANS le <form>
            submit = None
            for sub_sel in [
                'form button[type="submit"]',
                'form button.fr-btn',
                'button[aria-label="Envoyer la candidature spontanée"]',
                'button[data-tracking-id="postuler-entreprise-algo"]',
                'button[type="submit"][data-testid="candidature-not-sent"]',
                'button.fr-btn:has-text("envoie ma candidature")',
                'button[type="submit"]',
            ]:
                try:
                    loc = page.locator(sub_sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        submit = loc
                        txt = await loc.inner_text()
                        self._log(f"  🔘 Bouton submit: '{txt.strip()[:40]}' [{sub_sel}]")
                        break
                except Exception:
                    pass

            # Fallback: chercher le bouton bleu (fr-btn) qui n'est PAS le postuler
            if not submit:
                try:
                    all_btns = await page.evaluate(r"""
                        () => Array.from(document.querySelectorAll('form button.fr-btn, form button[type="submit"]'))
                            .filter(b => b.offsetParent !== null)
                            .filter(b => !/(fermer|close|partager|signaler)/i.test(b.textContent))
                            .map(b => ({
                                text: b.textContent.trim().substring(0,50),
                                testid: b.dataset.testid || '',
                                idx: Array.from(document.querySelectorAll('button')).indexOf(b)
                            }))
                    """)
                    self._log(f"  🔍 Boutons .fr-btn visibles: {all_btns}", "warning")
                    # Prendre le dernier bouton bleu visible (en bas du form)
                    if all_btns:
                        idx = all_btns[-1]["idx"]
                        submit = page.locator("button").nth(idx)
                        self._log(f"  🔘 Fallback submit: '{all_btns[-1]['text']}'")
                except Exception as e:
                    self._log(f"  🔍 Erreur fallback: {e}", "warning")

            if not submit:
                self._log("  ❌ Bouton soumettre introuvable", "error")
                btn_debug = await page.evaluate(r"""
                    () => Array.from(document.querySelectorAll('button'))
                        .filter(b => b.offsetParent !== null)
                        .map(b => ({text: b.textContent.trim().substring(0,40), type: b.type, testid: b.dataset.testid||'', cls: b.className.substring(0,30)}))
                        .slice(0, 10)
                """)
                self._log(f"  🔍 Tous les boutons: {btn_debug}", "warning")
                return False

            # ── Attendre que le bouton soit activé ──
            try:
                await submit.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                is_disabled = await submit.is_disabled()
                if is_disabled:
                    self._log("  ⏳ Bouton désactivé, attente upload CV…")
                    for _ in range(30):
                        await asyncio.sleep(2)
                        if not await submit.is_disabled():
                            self._log("  ✅ Bouton activé !")
                            break
                    else:
                        self._log("  ⚠️  Bouton toujours désactivé après 60s", "warning")
            except Exception:
                pass

            # ── Clic submit ──
            self._log("  🖱️  Clic sur le bouton submit…")
            try:
                await submit.click(timeout=15_000)
            except Exception:
                self._log("  🔄 Clic JS fallback")
                try:
                    await submit.evaluate("el => el.click()")
                except Exception:
                    # Dernier recours: clic via coordonnées
                    box = await submit.bounding_box()
                    if box:
                        await page.mouse.click(
                            box["x"] + box["width"] / 2,
                            box["y"] + box["height"] / 2,
                        )
                        self._log("  🖱️  Clic coordonnées")

            # ── Vérifier le résultat ──
            self._log("  ⏳ Attente confirmation…")
            await asyncio.sleep(15)

            body_text = await page.inner_text("body")
            body_lower = body_text.lower()

            if "vous avez atteint" in body_lower:
                self._log("  🛑 LIMITE ATTEINTE (post-submit)", "warning")
                self._handle_rate_limit()
                return False

            # Vérifier succès — data-testid
            for success_sel in [
                '[data-testid="application-success"]',
                '[data-testid="candidature-sent"]',
                '[data-testid="candidature-success"]',
                '.fr-alert--success',
            ]:
                el = await page.query_selector(success_sel)
                if el:
                    self._log(f"  ✅ Succès détecté via {success_sel}")
                    return True

            # Vérifier succès — texte dans la page
            success_patterns = [
                "a bien été envoyée",
                "candidature envoyée",
                "votre candidature a été",
                "merci pour votre candidature",
                "mail a été envoyé",
                "bien été transmise",
                "candidature a été transmise",
                "votre message a été envoyé",
                "envoyée avec succès",
                "félicitations",
            ]
            for pattern in success_patterns:
                if pattern in body_lower:
                    self._log(f"  ✅ Succès détecté: '{pattern}'")
                    return True

            # Vérifier si le bouton postuler a disparu (= form soumis, modal fermé)
            postuler_gone = True
            try:
                loc = page.locator('[data-testid="candidature-not-sent"]').first
                if await loc.count() > 0 and await loc.is_visible():
                    postuler_gone = False
            except Exception:
                pass
            if postuler_gone:
                # Le form a peut-être été soumis et fermé
                # Vérifier si le bouton est devenu "candidature-sent"
                sent_el = await page.query_selector('[data-testid="candidature-sent"]')
                if sent_el:
                    self._log("  ✅ Succès: bouton devenu candidature-sent")
                    return True

            self._log("  ⚠️  Pas de confirmation détectée", "warning")
            snippet = body_text[:500].replace('\n', ' ')
            self._log(f"  🔍 Page: {snippet[:200]}", "warning")
            return False

        except Exception as exc:
            self._log(f"  ❌ Formulaire: {exc}", "error")
            return False

    def stop(self) -> None:
        self.stop_event.set()
