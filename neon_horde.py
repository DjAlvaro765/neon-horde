import pygame
import random
import math
import array

W, H = 900, 600
FPS = 60
DT = 1 / FPS
HS_FILE = "highscore.txt"

pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()
screen = pygame.display.set_mode((W, H))
world = pygame.Surface((W, H))
pygame.display.set_caption("Neon Horde")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 28)
small = pygame.font.SysFont(None, 22)
big = pygame.font.SysFont(None, 72)


# ---------- Sonidos generados por código (no hacen falta archivos) ----------
def make_sound(freq, dur, vol=0.2, slide=0.0, kind="sine"):
    rate = 22050
    n = int(rate * dur)
    buf = array.array("h")
    for i in range(n):
        t = i / rate
        env = 1 - i / n
        if kind == "noise":
            v = random.uniform(-1, 1)
        elif kind == "square":
            v = 1 if math.sin(2 * math.pi * (freq + slide * t) * t) > 0 else -1
        else:
            v = math.sin(2 * math.pi * (freq + slide * t) * t)
        buf.append(int(v * env * vol * 32767))
    return pygame.mixer.Sound(buffer=buf.tobytes())


try:
    SND = {
        "disparo": make_sound(700, 0.06, 0.05, -4000, "square"),
        "golpe": make_sound(0, 0.04, 0.07, kind="noise"),
        "explosion": make_sound(0, 0.18, 0.14, kind="noise"),
        "gema": make_sound(900, 0.05, 0.10, 6000),
        "nivel": make_sound(500, 0.35, 0.22, 900),
        "dano": make_sound(150, 0.2, 0.22, -300, "square"),
        "nova": make_sound(200, 0.3, 0.22, 800),
        "jefe": make_sound(90, 0.6, 0.28, 0, "square"),
    }
except Exception:
    SND = {}


def play(nombre):
    s = SND.get(nombre)
    if s:
        s.play()


# ---------- Datos del juego ----------
TIPOS = {
    "normal": {"color": (220, 70, 70), "hp": 1, "vel": 1.0, "r": 12, "dmg": 10},
    "rapido": {"color": (255, 150, 50), "hp": 1, "vel": 2.0, "r": 9, "dmg": 8},
    "tanque": {"color": (170, 80, 220), "hp": 8, "vel": 0.7, "r": 20, "dmg": 15},
    "jefe": {"color": (255, 60, 120), "hp": 120, "vel": 0.9, "r": 38, "dmg": 25},
}

UPGRADES = [
    ("speed", "Más velocidad", "Te mueves más rápido"),
    ("rate", "Disparo más rápido", "Menos tiempo entre disparos"),
    ("damage", "Más daño", "Todas tus armas pegan más fuerte"),
    ("multi", "Disparo extra", "Un proyectil más por ráfaga"),
    ("magnet", "Imán de XP", "Atraes los cristales desde más lejos"),
    ("health", "+30 de vida", "Vida máxima y curación"),
    ("orbs", "Orbitales", "Esferas que giran y dañan a tu alrededor"),
    ("nova", "Onda expansiva", "Explosión periódica que daña a todos cerca"),
    ("pierce", "Balas perforantes", "Tus balas atraviesan enemigos"),
]


def load_hs():
    try:
        with open(HS_FILE) as f:
            return int(f.read())
    except (OSError, ValueError):
        return 0


def save_hs(v):
    try:
        with open(HS_FILE, "w") as f:
            f.write(str(v))
    except OSError:
        pass


def texto(msg, fuente, color, x, y, centro=False):
    surf = fuente.render(msg, True, color)
    rect = surf.get_rect()
    if centro:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    screen.blit(surf, rect)


class Enemigo:
    def __init__(self, tipo, pos, hp, vel):
        t = TIPOS[tipo]
        self.tipo = tipo
        self.pos = pos
        self.hp = hp
        self.maxhp = hp
        self.vel = vel
        self.r = t["r"]
        self.color = t["color"]
        self.dmg = t["dmg"]
        self.orb_cd = 0.0
        self.flash = 0.0


class Juego:
    def __init__(self):
        self.highscore = load_hs()
        self.reiniciar()
        self.estado = "titulo"

    def reiniciar(self):
        self.pos = pygame.Vector2(W / 2, H / 2)
        self.maxhp = 100
        self.hp = 100
        self.speed = 3.2
        self.rate = 0.6
        self.damage = 1
        self.multi = 1
        self.magnet = 80
        self.orbs = 0
        self.nova = 0
        self.pierce = 0
        self.orb_r = 65
        self.ang = 0.0
        self.nova_t = 3.0
        self.cool = 0.0
        self.hit_cd = 0.0
        self.shake = 0.0
        self.aviso = 0.0
        self.balas = []
        self.enemigos = []
        self.gemas = []
        self.particulas = []
        self.anillos = []
        self.xp = 0
        self.need = 5
        self.nivel = 1
        self.tiempo = 0.0
        self.kills = 0
        self.bonus = 0
        self.spawn_t = 0.0
        self.next_boss = 90.0
        self.estado = "juego"
        self.opciones = []
        self.score = 0

    # ---------- Utilidades ----------
    def burst(self, pos, color, n):
        for _ in range(n):
            ang = random.uniform(0, 2 * math.pi)
            vel = pygame.Vector2(math.cos(ang), math.sin(ang)) * random.uniform(1, 5)
            vida = random.uniform(0.25, 0.6)
            self.particulas.append([pos.copy(), vel, vida, vida, color, random.uniform(2, 4)])

    def danar(self, e, cantidad):
        e.hp -= cantidad
        e.flash = 0.08
        self.burst(e.pos, e.color, 2)
        play("golpe")

    def orb_positions(self):
        res = []
        for i in range(self.orbs):
            a = self.ang + 2 * math.pi * i / self.orbs
            res.append(self.pos + pygame.Vector2(math.cos(a), math.sin(a)) * self.orb_r)
        return res

    def aplicar(self, clave):
        if clave == "speed":
            self.speed += 0.4
        elif clave == "rate":
            self.rate = max(0.1, self.rate * 0.82)
        elif clave == "damage":
            self.damage += 1
        elif clave == "multi":
            self.multi += 1
        elif clave == "magnet":
            self.magnet += 50
        elif clave == "health":
            self.maxhp += 30
            self.hp = min(self.maxhp, self.hp + 30)
        elif clave == "orbs":
            self.orbs += 1
        elif clave == "nova":
            self.nova += 1
        elif clave == "pierce":
            self.pierce += 1
        self.estado = "juego"

    # ---------- Acciones ----------
    def spawn(self, tipo=None):
        if tipo is None:
            pesos = {"normal": 10, "rapido": 0, "tanque": 0}
            if self.tiempo > 20:
                pesos["rapido"] = min(6, (self.tiempo - 20) / 10)
            if self.tiempo > 50:
                pesos["tanque"] = min(3, (self.tiempo - 50) / 20)
            tipo = random.choices(list(pesos), weights=list(pesos.values()))[0]
        lado = random.choice("udlr")
        if lado == "u":
            p = pygame.Vector2(random.uniform(0, W), -40)
        elif lado == "d":
            p = pygame.Vector2(random.uniform(0, W), H + 40)
        elif lado == "l":
            p = pygame.Vector2(-40, random.uniform(0, H))
        else:
            p = pygame.Vector2(W + 40, random.uniform(0, H))
        base = TIPOS[tipo]
        hp = max(1, int(base["hp"] * (1 + self.tiempo / 60)))
        vel = min(3.2, base["vel"] * (0.9 + random.random() * 0.4) + self.tiempo * 0.002)
        self.enemigos.append(Enemigo(tipo, p, hp, vel))

    def disparar(self):
        orden = sorted(self.enemigos, key=lambda e: e.pos.distance_to(self.pos))
        for i in range(self.multi):
            objetivo = orden[i % len(orden)]
            d = objetivo.pos - self.pos
            if d.length() == 0:
                continue
            self.balas.append({
                "p": self.pos.copy(),
                "v": d.normalize() * 9,
                "life": 1.5,
                "pierce": self.pierce,
                "hit": set(),
            })
        play("disparo")

    def lanzar_nova(self):
        radio = 110 + 20 * self.nova
        for e in self.enemigos:
            if e.pos.distance_to(self.pos) < radio + e.r:
                self.danar(e, 2 + self.nova + self.damage)
        self.anillos.append([0.0, radio])
        play("nova")

    # ---------- Lógica ----------
    def actualizar(self):
        self.tiempo += DT
        self.ang += 2.5 * DT
        self.shake = max(0.0, self.shake - DT)
        self.aviso = max(0.0, self.aviso - DT)

        # Movimiento del jugador
        k = pygame.key.get_pressed()
        mov = pygame.Vector2(
            (k[pygame.K_d] or k[pygame.K_RIGHT]) - (k[pygame.K_a] or k[pygame.K_LEFT]),
            (k[pygame.K_s] or k[pygame.K_DOWN]) - (k[pygame.K_w] or k[pygame.K_UP]),
        )
        if mov.length() > 0:
            self.pos += mov.normalize() * self.speed
        self.pos.x = max(10, min(W - 10, self.pos.x))
        self.pos.y = max(10, min(H - 10, self.pos.y))

        # Disparo automático
        self.cool -= DT
        if self.cool <= 0 and self.enemigos:
            self.disparar()
            self.cool = self.rate

        # Onda expansiva
        if self.nova > 0:
            self.nova_t -= DT
            if self.nova_t <= 0:
                self.lanzar_nova()
                self.nova_t = max(2.0, 5.0 - 0.6 * self.nova)

        # Aparición de enemigos
        self.spawn_t -= DT
        if self.spawn_t <= 0:
            self.spawn()
            self.spawn_t = max(0.12, 0.9 - self.tiempo * 0.008)
        if self.tiempo >= self.next_boss:
            self.spawn("jefe")
            self.next_boss += 90
            self.aviso = 2.5
            play("jefe")

        # Balas
        for b in self.balas:
            b["p"] += b["v"]
            b["life"] -= DT

        # Enemigos
        self.hit_cd -= DT
        for e in self.enemigos:
            e.orb_cd -= DT
            e.flash -= DT
            d = self.pos - e.pos
            dist = d.length()
            if dist > 0:
                e.pos += d.normalize() * e.vel
            if dist < e.r + 10 and self.hit_cd <= 0:
                self.hp -= e.dmg
                self.hit_cd = 0.5
                self.shake = 0.2
                self.burst(self.pos, (255, 80, 80), 12)
                play("dano")

        # Balas contra enemigos
        for b in self.balas:
            for e in self.enemigos:
                if e in b["hit"]:
                    continue
                if b["p"].distance_to(e.pos) < e.r + 4:
                    self.danar(e, self.damage)
                    b["hit"].add(e)
                    if b["pierce"] > 0:
                        b["pierce"] -= 1
                    else:
                        b["life"] = 0
                        break
        self.balas = [b for b in self.balas if b["life"] > 0]

        # Orbitales
        for op in self.orb_positions():
            for e in self.enemigos:
                if e.orb_cd <= 0 and op.distance_to(e.pos) < e.r + 8:
                    self.danar(e, self.damage)
                    e.orb_cd = 0.4

        # Enemigos muertos
        vivos = []
        for e in self.enemigos:
            if e.hp <= 0:
                self.kills += 1
                es_jefe = e.tipo == "jefe"
                for _ in range(15 if es_jefe else 1):
                    offset = pygame.Vector2(random.uniform(-25, 25), random.uniform(-25, 25)) if es_jefe else pygame.Vector2()
                    self.gemas.append(e.pos + offset)
                self.burst(e.pos, e.color, 30 if es_jefe else 10)
                play("explosion")
                if es_jefe:
                    self.shake = 0.5
                    self.bonus += 200
            else:
                vivos.append(e)
        self.enemigos = vivos

        # Gemas
        restantes = []
        recogida = False
        for g in self.gemas:
            d = self.pos - g
            dist = d.length()
            if 0 < dist < self.magnet:
                g += d.normalize() * 6
            if dist < 14:
                self.xp += 1
                recogida = True
            else:
                restantes.append(g)
        self.gemas = restantes
        if recogida:
            play("gema")

        # Partículas y anillos
        for p in self.particulas:
            p[0] += p[1]
            p[1] *= 0.92
            p[2] -= DT
        self.particulas = [p for p in self.particulas if p[2] > 0]
        for a in self.anillos:
            a[0] += 10
        self.anillos = [a for a in self.anillos if a[0] < a[1]]

        # Subir de nivel
        if self.xp >= self.need:
            self.xp = 0
            self.nivel += 1
            self.need = int(self.need * 1.4) + 2
            self.opciones = random.sample(UPGRADES, 3)
            self.estado = "nivel"
            play("nivel")

        # Muerte
        if self.hp <= 0:
            self.score = self.kills * 10 + int(self.tiempo) + self.bonus
            if self.score > self.highscore:
                self.highscore = self.score
                save_hs(self.score)
            self.estado = "muerto"

    # ---------- Dibujo ----------
    def dibujar(self):
        world.fill((14, 14, 24))
        for x in range(0, W, 60):
            pygame.draw.line(world, (22, 22, 38), (x, 0), (x, H))
        for y in range(0, H, 60):
            pygame.draw.line(world, (22, 22, 38), (0, y), (W, y))

        for g in self.gemas:
            pygame.draw.circle(world, (80, 220, 255), g, 4)
        for e in self.enemigos:
            color = (255, 255, 255) if e.flash > 0 else e.color
            pygame.draw.circle(world, color, e.pos, e.r)
            if e.maxhp > 3 and e.hp < e.maxhp:
                ancho = e.r * 2
                x0 = e.pos.x - e.r
                y0 = e.pos.y - e.r - 8
                pygame.draw.rect(world, (60, 20, 20), (x0, y0, ancho, 4))
                pygame.draw.rect(world, (90, 230, 90), (x0, y0, ancho * max(0, e.hp) / e.maxhp, 4))
        for b in self.balas:
            pygame.draw.circle(world, (255, 230, 90), b["p"], 4)
        for a in self.anillos:
            pygame.draw.circle(world, (120, 200, 255), self.pos, a[0], 3)
        for op in self.orb_positions():
            pygame.draw.circle(world, (140, 220, 255), op, 8)
            pygame.draw.circle(world, (255, 255, 255), op, 8, 1)
        for p in self.particulas:
            r = max(1, int(p[5] * p[2] / p[3]))
            pygame.draw.circle(world, p[4], p[0], r)

        parpadeo = self.hit_cd > 0 and int(self.tiempo * 20) % 2 == 0
        pygame.draw.circle(world, (255, 255, 255) if parpadeo else (90, 220, 130), self.pos, 12)

        # Pantalla con temblor
        ox = oy = 0
        if self.shake > 0:
            ox = random.randint(-5, 5)
            oy = random.randint(-5, 5)
        screen.fill((0, 0, 0))
        screen.blit(world, (ox, oy))

        if self.estado != "titulo":
            self.dibujar_hud()

        if self.estado == "titulo":
            self.pantalla_titulo()
        elif self.estado == "nivel":
            self.pantalla_nivel()
        elif self.estado == "pausa":
            self.velo(150)
            texto("PAUSA", big, (255, 255, 255), W / 2, H / 2 - 20, True)
            texto("Presiona P para continuar", font, (200, 200, 200), W / 2, H / 2 + 40, True)
        elif self.estado == "muerto":
            self.velo(190)
            texto("GAME OVER", big, (230, 70, 70), W / 2, 180, True)
            texto(f"Puntos: {self.score}   (récord {self.highscore})", font, (255, 255, 255), W / 2, 260, True)
            texto(f"Nivel {self.nivel}  |  Bajas {self.kills}  |  Tiempo {self.tiempo_txt()}",
                  small, (180, 180, 200), W / 2, 295, True)
            texto("Presiona R para jugar otra vez", font, (255, 230, 90), W / 2, 350, True)

    def tiempo_txt(self):
        m, s = divmod(int(self.tiempo), 60)
        return f"{m:02d}:{s:02d}"

    def velo(self, alpha):
        v = pygame.Surface((W, H), pygame.SRCALPHA)
        v.fill((0, 0, 0, alpha))
        screen.blit(v, (0, 0))

    def dibujar_hud(self):
        pygame.draw.rect(screen, (60, 20, 20), (10, 10, 200, 14))
        pygame.draw.rect(screen, (220, 60, 60), (10, 10, 200 * max(0, self.hp) / self.maxhp, 14))
        pygame.draw.rect(screen, (20, 40, 60), (10, 28, 200, 8))
        pygame.draw.rect(screen, (80, 220, 255), (10, 28, 200 * self.xp / self.need, 8))
        texto(f"Nivel {self.nivel}", font, (255, 255, 255), 10, 42)
        texto(self.tiempo_txt(), font, (255, 255, 255), W / 2, 18, True)
        texto(f"Bajas: {self.kills}", font, (255, 255, 255), W - 140, 10)
        texto(f"Récord: {self.highscore}", font, (255, 220, 120), W - 140, 36)
        if self.aviso > 0:
            texto("¡LLEGA UN JEFE!", big, (255, 60, 120), W / 2, 90, True)

    def pantalla_titulo(self):
        self.velo(160)
        texto("NEON HORDE", big, (90, 230, 160), W / 2, 150, True)
        texto("Sobrevive a la horda. Mejora. Repite.", font, (200, 200, 220), W / 2, 215, True)
        texto("WASD o flechas: moverte (disparas solo)", small, (255, 255, 255), W / 2, 290, True)
        texto("1 / 2 / 3: elegir mejora    P: pausa", small, (255, 255, 255), W / 2, 320, True)
        texto(f"Récord: {self.highscore}", font, (255, 220, 120), W / 2, 380, True)
        texto("Presiona ENTER para empezar", font, (255, 230, 90), W / 2, 440, True)

    def pantalla_nivel(self):
        self.velo(170)
        texto("¡SUBES DE NIVEL!", big, (255, 230, 90), W / 2, 110, True)
        for i, (clave, nombre, desc) in enumerate(self.opciones):
            y = 235 + i * 95
            pygame.draw.rect(screen, (40, 50, 80), (W / 2 - 260, y - 38, 520, 76), border_radius=10)
            extra = ""
            if clave in ("orbs", "nova", "pierce"):
                extra = f"  (nv {getattr(self, clave) + 1})"
            texto(f"{i + 1}. {nombre}{extra}", font, (255, 255, 255), W / 2, y - 10, True)
            texto(desc, small, (170, 190, 220), W / 2, y + 16, True)


juego = Juego()
corriendo = True
while corriendo:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            corriendo = False
        elif ev.type == pygame.KEYDOWN:
            if juego.estado == "titulo" and ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                juego.reiniciar()
            elif juego.estado == "nivel" and ev.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                juego.aplicar(juego.opciones[ev.key - pygame.K_1][0])
            elif juego.estado == "muerto" and ev.key == pygame.K_r:
                juego.reiniciar()
            elif ev.key == pygame.K_p and juego.estado in ("juego", "pausa"):
                juego.estado = "pausa" if juego.estado == "juego" else "juego"

    if juego.estado == "juego":
        juego.actualizar()
    juego.dibujar()
    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
