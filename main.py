
import argparse
import pygame as pg, random, math, os, sys
from enum import Enum


class GameMode(Enum):
    """Supported game modes."""
    SPEED = "speed"
    GROWTH = "growth"

GRID_W, GRID_H = 22, 26
CELL = 28
PAD  = 56
TOP  = 34
W, H = GRID_W*CELL + PAD*2, GRID_H*CELL + PAD*2 + TOP
FPS  = 60

SPEED_BASE = 6.0

# Duraciones
SLOW_DUR  = 4.0
MAG_DUR   = 6.0
TURBO_DUR = 2.5
COMBO_WIN = 4.0
COMBO_COUNT = 3

THEME = {
 "bg1": (250,236,214),
 "bg2": (243,221,190),
 "grid": (210,180,150),
 "ink" : (90,65,40),
 "straw": (230,70,50),
 "straw_seed": (255,190,90),
 "leaf": (70,150,80),
 "blue": (100,108,160),
 "gold": (240,200,70)
}

def grid_to_px(x,y): return (PAD + x*CELL + CELL//2, TOP + PAD + y*CELL + CELL//2)

def vignette(w,h, strength=160):
    s = pg.Surface((w,h), pg.SRCALPHA)
    cx,cy=w/2,h/2; rad=math.hypot(cx,cy)
    arr = pg.surfarray.pixels_alpha(s)
    # small vectorized-ish loop
    for y in range(h):
        for x in range(w):
            a = math.hypot(x-cx,y-cy)/rad
            arr[x,y] = max(0, min(255, int((a**1.8)*strength)))
    del arr
    return s

class Player:
    def __init__(self, surf, wrap=False):
        self.cell=(GRID_W//2, GRID_H//2)
        self.dir=(1,0); self.wrap=wrap
        self.surf = surf
        self.angle = 0.0
        self.wag_t = 0.0
    def set_dir(self,d): 
        if d!=(0,0): self.dir=d
    def step(self):
        x,y=self.cell; nx,ny=x+self.dir[0], y+self.dir[1]
        if self.wrap: nx%=GRID_W; ny%=GRID_H
        else:
            if nx<0 or ny<0 or nx>=GRID_W or ny>=GRID_H: return False
        self.cell=(nx,ny)
        if   self.dir==(1,0): self.angle=0
        elif self.dir==(-1,0): self.angle=180
        elif self.dir==(0,-1): self.angle=90
        elif self.dir==(0,1): self.angle=270
        return True
    def draw(self, sc, speed):
        # animación wag (oscilación ligera según velocidad)
        self.wag_t += 0.1 + speed*0.02
        wobble = math.sin(self.wag_t)*4
        x,y = grid_to_px(*self.cell)
        img=pg.transform.smoothscale(self.surf,(int(CELL*1.2),int(CELL*1.2)))
        img=pg.transform.rotate(img, self.angle + wobble)
        rect=img.get_rect(center=(x,y))
        sc.blit(img,rect)

class Game:
    def __init__(self, screen, mode: GameMode = GameMode.SPEED):
        self.sc=screen; self.clock=pg.time.Clock()
        self.font=pg.font.SysFont('consolas',18); self.big=pg.font.SysFont('consolas',32,bold=True)
        self.wrap=True
        self.mode=mode
        # load panda
        base=pg.image.load(os.path.join('assets','panda.png')).convert_alpha()
        w,h=base.get_size()
        crop=base.subsurface((0,0,w//2,h)) # recorta lado izq. (panda grande)
        self.panda=crop
        # sfx
        names=['eat','die','bonus','count','start','power','turbo']
        self.sfx={n:pg.mixer.Sound(os.path.join('assets','sfx',f'{n}.wav')) for n in names}
        self.vign=vignette(W,H,150)
        self.state='menu'
        self.reset()
    def reset(self):
        self.player=Player(self.panda, wrap=self.wrap)
        self.score=0; self.speed=SPEED_BASE; self.acc=0.0
        # efectos temporales
        self.slow_t=0.0; self.mag_t=0.0; self.turbo_t=0.0
        # combo
        self.combo=0; self.combo_timer=0.0
        self.fruit=None; self.power=None
        if self.mode == GameMode.GROWTH:
            self.body=[self.player.cell]
            self.len=3
        else:
            self.body=[]
            self.len=0
        self.spawn_fruit(); self.spawn_power(chance=0.35)
        self._cnt=3
    def spawn_fruit(self):
        occ={self.player.cell}
        if self.mode == GameMode.GROWTH:
            occ.update(self.body)
        while True:
            c=(random.randrange(GRID_W), random.randrange(GRID_H))
            if c not in occ: self.fruit=c; return
    def spawn_power(self, chance=0.25):
        if random.random()>chance: self.power=None; return
        kinds=['slow','magnet']; kind=random.choice(kinds)
        occ={self.player.cell, self.fruit} if self.fruit else {self.player.cell}
        if self.mode == GameMode.GROWTH:
            occ.update(self.body)
        while True:
            c=(random.randrange(GRID_W), random.randrange(GRID_H))
            if c not in occ: self.power=(kind,c); return
    def draw_bg(self,t):
        g=pg.Surface((W,H))
        for y in range(H):
            k=y/H; col=[int(THEME['bg1'][i]*(1-k)+THEME['bg2'][i]*k) for i in range(3)]; g.fill(col,(0,y,W,1))
        self.sc.blit(g,(0,0))
        gc=THEME['grid']; osc=math.sin(t*0.5)*1.2
        for x in range(GRID_W+1):
            x1=PAD+x*CELL+osc; pg.draw.line(self.sc,gc,(x1,TOP+PAD),(x1,TOP+PAD+GRID_H*CELL),1)
        for y in range(GRID_H+1):
            y1=TOP+PAD+y*CELL+osc; pg.draw.line(self.sc,gc,(PAD,y1),(PAD+GRID_W*CELL,y1),1)
        pg.draw.rect(self.sc,(0,0,0,180),(0,0,W,TOP))
        title=self.font.render("RED PANDA FRUIT DASH",True,THEME['ink'])
        self.sc.blit(title,(8,6))
        info=f"MODE: {self.mode.name} | SPEED x{self.speed/SPEED_BASE:.2f}"
        if self.mode==GameMode.GROWTH:
            info+=f" | LEN: {self.len}"
        info_r=self.font.render(info,True,THEME['ink'])
        self.sc.blit(info_r,(8+title.get_width()+20,6))
        self.sc.blit(self.font.render(f"{self.score:05d}",True,THEME['ink']),(W-70,6))
        # status power-ups
        xs=W-250; y=6
        if self.slow_t>0: self.sc.blit(self.font.render(f"Slow:{self.slow_t:0.1f}s",True,THEME['ink']),(xs,y)); y+=18
        if self.mag_t>0:  self.sc.blit(self.font.render(f"Mag:{self.mag_t:0.1f}s",True,THEME['ink']),(xs,y)); y+=18
        if self.turbo_t>0:self.sc.blit(self.font.render(f"Turbo:{self.turbo_t:0.1f}s",True,THEME['ink']),(xs,y))
    def draw_strawberry(self, cell):
        x,y = grid_to_px(*cell)
        r=int(CELL*0.42)
        pg.draw.polygon(self.sc, THEME['straw'],
            [(x, y-r),(x+r*0.85,y-r*0.2),(x,y+r),(x-r*0.85,y-r*0.2)])
        for dx,dy in [(-6,-2),(0,0),(6,-2),(-3,5),(3,5)]:
            pg.draw.circle(self.sc, THEME['straw_seed'], (int(x+dx),int(y+dy)), 2)
        pg.draw.polygon(self.sc, THEME['leaf'],
            [(x-6,y-r-3),(x+6,y-r-3),(x,y-r-10)])
    def draw_power(self):
        if not self.power: return
        kind,cell=self.power
        x,y=grid_to_px(*cell)
        if kind=='slow':
            # Hoja
            pg.draw.polygon(self.sc, THEME['leaf'], [(x-8,y),(x+8,y),(x,y-14)])
        elif kind=='magnet':
            # U-imán dorado
            pg.draw.arc(self.sc, THEME['gold'], (x-10,y-10,20,20), math.pi/4, 3*math.pi/4, 3)
            pg.draw.arc(self.sc, THEME['gold'], (x-6 ,y-10,12,20), math.pi/4, 3*math.pi/4, 3)
    def attract(self):
        # atrae fruta si mag está activo y cerca (r<=3 celdas taxicab)
        if self.mag_t<=0 or not self.fruit: return
        fx,fy=self.fruit; px,py=self.player.cell
        if abs(fx-px)+abs(fy-py)<=3:
            # mueve un paso hacia el jugador
            dx=1 if px>fx else -1 if px<fx else 0
            dy=1 if py>fy else -1 if py<fy else 0
            self.fruit=(fx+dx, fy+dy)
    def start_menu(self,dt):
        t=pg.time.get_ticks()/1000; self.draw_bg(t)
        msg=self.big.render("PRESS ENTER",True,THEME['ink']); self.sc.blit(msg,(W//2-msg.get_width()//2, H-64))
        hint=self.font.render("TAB: Wrap ON/OFF | M: Mode | Flechas/WASD para mover",True,THEME['ink'])
        self.sc.blit(hint,(W//2-hint.get_width()//2, H-36))
        self.sc.blit(self.vign,(0,0)); pg.display.flip()
        for e in pg.event.get():
            if e.type==pg.QUIT: pg.quit(); sys.exit()
            if e.type==pg.KEYDOWN:
                if e.key in (pg.K_RETURN, pg.K_SPACE): self.state='game'; self._cnt=3; self.sfx['count'].play()
                elif e.key==pg.K_TAB: self.wrap=not self.wrap; self.reset()
                elif e.key==pg.K_m:
                    self.mode = GameMode.GROWTH if self.mode==GameMode.SPEED else GameMode.SPEED
                    self.reset()
    def start_game(self,dt):
        t=pg.time.get_ticks()/1000; self.draw_bg(t)
        if self._cnt>0:
            cnt=self.big.render(str(self._cnt),True,THEME['ink'])
            self.sc.blit(cnt,(W//2-cnt.get_width()//2, H//2-20)); pg.display.flip()
            self.acc+=dt
            if self.acc>=1.0:
                self.acc=0.0; self._cnt-=1
                if self._cnt>0: self.sfx['count'].play()
                else: self.sfx['start'].play()
            for e in pg.event.get():
                if e.type==pg.QUIT: pg.quit(); sys.exit()
                if e.type==pg.KEYDOWN and e.key==pg.K_ESCAPE: self.state='menu'; self.reset()
            return
        for e in pg.event.get():
            if e.type==pg.QUIT: pg.quit(); sys.exit()
            if e.type==pg.KEYDOWN:
                if e.key==pg.K_ESCAPE: self.state='menu'; self.reset()
                elif e.key in (pg.K_UP, pg.K_w): self.player.set_dir((0,-1))
                elif e.key in (pg.K_DOWN, pg.K_s): self.player.set_dir((0,1))
                elif e.key in (pg.K_LEFT, pg.K_a): self.player.set_dir((-1,0))
                elif e.key in (pg.K_RIGHT, pg.K_d): self.player.set_dir((1,0))

        # timers
        self.slow_t = max(0.0, self.slow_t-dt)
        self.mag_t  = max(0.0, self.mag_t-dt)
        self.turbo_t= max(0.0, self.turbo_t-dt)
        if self.combo_timer>0: self.combo_timer=max(0.0, self.combo_timer-dt)
        else: self.combo=0

        # physics
        step_time = 1.0 / (self.speed * (0.55 if self.slow_t>0 else 1.0) * (1.45 if self.turbo_t>0 else 1.0))
        self.acc += dt
        while self.acc >= step_time:
            self.acc -= step_time
            if not self.player.step():
                self.sfx['die'].play(); self.state='menu'; self.reset(); return

            ate = self.fruit and self.player.cell == self.fruit

            if self.mode == GameMode.GROWTH:
                self.body.insert(0, self.player.cell)
                if ate:
                    self.len += 1
                if len(self.body) > self.len:
                    self.body.pop()
                if self.player.cell in self.body[1:]:
                    self.sfx['die'].play(); self.state='menu'; self.reset(); return

            if ate:
                self.score += 10; self.sfx['eat'].play()
                if self.mode == GameMode.SPEED:
                    self.speed = min(self.speed * 1.10, 2.5 * SPEED_BASE)
                else:
                    if (self.len-3) > 0 and (self.len-3) % 5 == 0:
                        self.speed = min(self.speed * 1.05, 1.8 * SPEED_BASE)
                # combo
                self.combo = self.combo+1 if self.combo_timer>0 else 1
                self.combo_timer = COMBO_WIN
                if self.combo>=COMBO_COUNT:
                    self.combo=0; self.combo_timer=0
                    self.turbo_t = TURBO_DUR; self.sfx['turbo'].play()
                    self.score += 20
                self.spawn_fruit()
                # 30% chance to spawn a power-up after eating
                self.spawn_power(chance=0.30)

            # power-up check
            if self.power and self.player.cell==self.power[1]:
                kind,_=self.power
                if kind=='slow': self.slow_t = SLOW_DUR
                elif kind=='magnet': self.mag_t = MAG_DUR
                self.sfx['power'].play()
                self.power=None

            # magnet attraction per tick
            self.attract()

        # draw
        if self.fruit: self.draw_strawberry(self.fruit)
        self.draw_power()
        if self.mode == GameMode.GROWTH:
            for i,cell in enumerate(self.body[1:],1):
                t=i/max(1,len(self.body)-1)
                col=tuple(int(THEME['straw'][j]*(1-t)+THEME['leaf'][j]*t) for j in range(3))
                x,y=grid_to_px(*cell)
                pg.draw.circle(self.sc,col,(x,y),int(CELL*0.35))
        self.player.draw(self.sc, self.speed)
        self.sc.blit(self.vign,(0,0))
        pg.display.flip()

    def run(self):
        while True:
            dt=self.clock.tick(FPS)/1000
            if self.state=='menu': self.start_menu(dt)
            else: self.start_game(dt)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode", choices=[m.value for m in GameMode], default="speed", help="Game mode")
    args=parser.parse_args()
    pg.init(); pg.mixer.init()
    pg.display.set_caption("Red Panda Fruit Dash v05")
    sc=pg.display.set_mode((W,H))
    Game(sc, mode=GameMode(args.mode)).run()

if __name__=="__main__":
    main()
