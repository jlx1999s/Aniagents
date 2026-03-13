import { useEffect, useRef, useState, useMemo } from 'react';
import '../styles/components.css';

const ROLE_MAPPING = {
  Scriptwriter_Agent: {
    roleId: 'sb_artist',
    name: '分镜师',
    color: '#61afef',
    hair: '#d19a66',
    accessory: 'glasses',
    deskX: 200,
    deskY: 280,
    action: '正在绘制分镜...',
    workLines: ['构图中', '镜头推进中', '节奏校对中']
  },
  Character_Designer_Agent: {
    roleId: 'char_designer',
    name: '角色设计',
    color: '#c678dd',
    hair: '#98c379',
    accessory: 'hair',
    deskX: 600,
    deskY: 280,
    action: '正在设定角色...',
    workLines: ['角色设定中', '服装细化中', '表情调试中']
  },
  Storyboard_Artist_Agent: {
    roleId: 'sb_drawer',
    name: '分镜画师',
    color: '#98c379',
    hair: '#e5c07b',
    accessory: 'pencil',
    deskX: 200,
    deskY: 420,
    action: '正在细化线稿...',
    workLines: ['线稿精修中', '透视校正中', '动作夸张中']
  },
  Animation_Artist_Agent: {
    roleId: 'video_editor',
    name: '视频师',
    color: '#e5c07b',
    hair: '#5c6370',
    accessory: 'headphones',
    deskX: 600,
    deskY: 420,
    action: '正在剪辑合成...',
    workLines: ['镜头拼接中', '节奏剪辑中', '特效合成中']
  }
};

const DIRECTOR_CONFIG = {
  roleId: 'director',
  name: '导演',
  color: '#e06c75',
  hair: '#282c34',
  accessory: 'beret',
  deskX: 400,
  deskY: 150,
  action: '正在统筹全局...',
  workLines: ['排期同步中', '质量复核中', '进度协调中']
};

const LOUNGE_AREA = { minX: 300, maxX: 500, minY: 480, maxY: 560 };
const ENV_LABELS = {
  space: '🌌 宇宙星空模式',
  day_clear: '☀️ 晴朗白天模式',
  day_rain: '🌧️ 阴雨绵绵模式',
  night_clear: '🌙 繁星都市模式',
  windy: '🍃 疾风掠过模式'
};

const rand = (min, max) => Math.random() * (max - min) + min;
const BOOK_COLORS = ['#e06c75', '#98c379', '#61afef', '#c678dd', '#e5c07b'];

function createBookshelfBooks() {
  const books = [];
  for (let shelf = 0; shelf < 3; shelf += 1) {
    let x = 6;
    while (x < 50) {
      if (Math.random() > 0.3) {
        const width = Math.floor(rand(4, 8));
        const height = Math.floor(rand(10, 14));
        const color = BOOK_COLORS[Math.floor(Math.random() * BOOK_COLORS.length)];
        books.push({ shelf, x, width, height, color });
        x += width + 1;
      } else {
        x += Math.floor(rand(5, 12));
      }
    }
  }
  return books;
}

function getAgentWorkLine(config) {
  const lines = Array.isArray(config.workLines) && config.workLines.length ? config.workLines : [config.action];
  return lines[Math.floor(Math.random() * lines.length)];
}

function resolveNodeStatus(snapshot, nodeName) {
  if (!snapshot) {
    return '';
  }
  if (snapshot.graph?.nodes?.[nodeName]?.status) {
    return snapshot.graph.nodes[nodeName].status;
  }
  if (Array.isArray(snapshot.nodeMetrics)) {
    const metric = snapshot.nodeMetrics.find((item) => item.node === nodeName);
    if (metric?.status) {
      return metric.status;
    }
  }
  if (Array.isArray(snapshot.executionPlan)) {
    const step = snapshot.executionPlan.find((item) => item.node === nodeName);
    if (step?.status) {
      return step.status;
    }
  }
  return '';
}

class Particle {
  constructor(x, y, type, color) {
    this.x = x;
    this.y = y;
    this.type = type;
    this.color = color;
    this.life = 1.0;
    this.vx = rand(-1, 1);
    this.vy = rand(-2, -0.5);
    this.size = rand(2, 4);

    if (type === 'zzz') {
      this.char = 'Z';
      this.size = rand(6, 10);
      this.vx = rand(0.2, 0.8);
      this.vy = rand(-1, -0.2);
    } else if (type === 'idea') {
      this.char = '!';
      this.size = 12;
      this.vx = 0;
      this.vy = -1;
    }
  }

  update() {
    this.x += this.vx;
    this.y += this.vy;
    this.life -= 0.02;
  }

  draw(ctx) {
    ctx.globalAlpha = Math.max(0, this.life);
    if (this.type === 'work') {
      ctx.fillStyle = this.color;
      ctx.fillRect(this.x, this.y, this.size, this.size);
    } else {
      ctx.fillStyle = this.color;
      ctx.font = `bold ${this.size}px "Press Start 2P"`;
      ctx.fillText(this.char, this.x, this.y);
    }
    ctx.globalAlpha = 1.0;
  }
}

class Agent {
  constructor(id, config) {
    this.id = id;
    this.config = config;
    this.x = rand(LOUNGE_AREA.minX, LOUNGE_AREA.maxX);
    this.y = rand(LOUNGE_AREA.minY, LOUNGE_AREA.maxY);
    this.targetX = this.x;
    this.targetY = this.y;
    this.speed = 1.5;
    this.state = 'wander';
    this.facing = 'front';
    this.walkCycle = 0;
    this.isWalking = false;
    this.speechBubble = null;
    this.speechTimer = 0;
    this.speechCooldown = rand(800, 2200);
    this.subState = 'wander_idle';
    this.actionTimer = 0;
  }

  say(text, duration = 3000) {
    this.speechBubble = text;
    this.speechTimer = duration;
  }

  update(dt, desiredState) {
    let enteredWorking = false;
    if (desiredState === 'working' && this.state !== 'working' && this.state !== 'going_to_desk') {
      this.state = 'going_to_desk';
      this.targetX = this.config.deskX;
      this.targetY = this.config.deskY + 8;
      this.subState = 'work_type';
    } else if (desiredState !== 'working' && this.state !== 'wander') {
      this.state = 'wander';
      this.targetX = rand(LOUNGE_AREA.minX, LOUNGE_AREA.maxX);
      this.targetY = rand(LOUNGE_AREA.minY, LOUNGE_AREA.maxY);
      this.subState = 'wander_idle';
      this.actionTimer = rand(1200, 2800);
      this.speechBubble = null;
      this.speechTimer = 0;
      this.speechCooldown = rand(1800, 3000);
    }

    if (this.speechTimer > 0) {
      this.speechTimer -= dt;
      if (this.speechTimer <= 0) this.speechBubble = null;
    }
    this.speechCooldown -= dt;

    const dx = this.targetX - this.x;
    const dy = this.targetY - this.y;
    const dist = Math.sqrt(dx * dx + dy * dy);

    if (dist > 2) {
      this.isWalking = true;
      this.x += (dx / dist) * this.speed;
      this.y += (dy / dist) * this.speed;
      this.walkCycle += 0.3;

      if (Math.abs(dx) > Math.abs(dy)) {
        this.facing = dx > 0 ? 'right' : 'left';
      } else {
        this.facing = dy > 0 ? 'front' : 'back';
      }
    } else {
      this.x = this.targetX;
      this.y = this.targetY;
      this.isWalking = false;
      this.walkCycle = 0;

      if (this.state === 'going_to_desk') {
        this.state = 'working';
        this.subState = 'work_type';
        this.actionTimer = rand(2200, 5200);
        this.facing = 'back';
        this.say(getAgentWorkLine(this.config), rand(1500, 2400));
        this.speechCooldown = rand(1500, 2600);
        enteredWorking = true;
      } else if (this.state === 'wander') {
        if (this.actionTimer > 0) {
          this.actionTimer -= dt;
        } else {
          const r = Math.random();
          if (r < 0.42) {
            this.targetX = Math.max(LOUNGE_AREA.minX, Math.min(LOUNGE_AREA.maxX, this.x + rand(-40, 40)));
            this.targetY = Math.max(LOUNGE_AREA.minY, Math.min(LOUNGE_AREA.maxY, this.y + rand(-40, 40)));
            this.subState = 'wander_walk';
            this.actionTimer = rand(800, 1600);
          } else if (r < 0.72) {
            this.subState = 'wander_idle';
            this.actionTimer = rand(1800, 4200);
          } else {
            this.subState = 'wander_drink';
            this.actionTimer = rand(2400, 4600);
            this.facing = 'front';
          }
        }
      } else if (this.state === 'working') {
        this.actionTimer -= dt;
        if (this.actionTimer <= 0) {
          if (this.subState === 'work_type') {
            this.subState = 'work_think';
            this.actionTimer = rand(1700, 3200);
          } else {
            this.subState = 'work_type';
            this.actionTimer = rand(2600, 5200);
          }
        }
      }
    }

    if (this.state === 'working' && this.speechTimer <= 0 && this.speechCooldown <= 0) {
      this.say(getAgentWorkLine(this.config), rand(1500, 2400));
      this.speechCooldown = rand(1500, 3200);
    }

    return {
      enteredWorking,
      spawnWorkParticle: this.state === 'working' && this.subState === 'work_type' && Math.random() < 0.1,
      spawnIdeaParticle: this.state === 'working' && this.subState === 'work_think' && Math.random() < 0.012,
      spawnZzzParticle: this.state === 'wander' && !this.isWalking && this.subState === 'wander_idle' && Math.random() < 0.01
    };
  }

  draw(ctx) {
    ctx.save();
    ctx.translate(this.x, this.y);

    const headW = 16, headH = 14;
    const bodyW = 14, bodyH = 12;
    const legW = 4, legH = 8;

    const isSitting = this.state === 'working';
    const sitOffset = isSitting ? 5 : 0;
    if (!isSitting) {
      ctx.fillStyle = 'rgba(0,0,0,0.3)';
      ctx.beginPath();
      ctx.ellipse(0, 5, 12, 4, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    let bobY = this.isWalking ? Math.abs(Math.sin(this.walkCycle)) * 2 : 0;
    let leftLegY = 0, rightLegY = 0;
    if (this.isWalking) {
      leftLegY = -Math.sin(this.walkCycle) * 3;
      rightLegY = Math.sin(this.walkCycle) * 3;
    }
    const shakeX = isSitting && this.subState === 'work_type' ? rand(-0.5, 0.5) : 0;
    ctx.translate(shakeX, -bobY + sitOffset);

    if (!isSitting) {
      ctx.fillStyle = '#282c34';
      if (this.facing === 'left' || this.facing === 'right') {
        ctx.fillRect(-2, -legH + leftLegY, legW + 2, legH);
      } else {
        ctx.fillRect(-6, -legH + leftLegY, legW, legH);
        ctx.fillRect(2, -legH + rightLegY, legW, legH);
      }
    }

    ctx.fillStyle = this.config.color;
    ctx.fillRect(-bodyW / 2, -legH - bodyH, bodyW, bodyH);
    ctx.fillStyle = 'rgba(0,0,0,0.15)';
    ctx.fillRect(-bodyW / 2, -legH - bodyH / 2, bodyW, bodyH / 2);

    let lArmY = this.isWalking ? Math.sin(this.walkCycle) * 3 : 0;
    let rArmY = this.isWalking ? -Math.sin(this.walkCycle) * 3 : 0;
    if (isSitting && this.subState === 'work_type') {
      lArmY = rand(-2, 2);
      rArmY = rand(-2, 2);
    }

    ctx.fillStyle = this.config.color;
    if (this.facing === 'front' || this.facing === 'back') {
      ctx.fillRect(-bodyW / 2 - 3, -legH - bodyH + 1 + lArmY, 3, bodyH - 2);
      if (this.subState === 'wander_drink' && this.facing === 'front') {
        ctx.fillRect(bodyW / 2, -legH - bodyH + 1, 3, bodyH / 2);
        ctx.fillStyle = '#eceff4';
        ctx.fillRect(2, -legH - bodyH - 3, 5, 6);
        ctx.fillStyle = '#5e81ac';
        ctx.fillRect(2, -legH - bodyH - 1, 5, 2);
      } else {
        ctx.fillStyle = this.config.color;
        ctx.fillRect(bodyW / 2, -legH - bodyH + 1 + rArmY, 3, bodyH - 2);
      }
    } else if (this.facing === 'left') {
      ctx.fillRect(-2, -legH - bodyH + 1 + lArmY, 4, bodyH - 2);
    } else if (this.facing === 'right') {
      ctx.fillRect(-2, -legH - bodyH + 1 + rArmY, 4, bodyH - 2);
    }

    ctx.translate(0, -legH - bodyH);
    ctx.fillStyle = '#ffceb4';
    ctx.fillRect(-headW / 2, -headH, headW, headH);

    // Hair
    ctx.fillStyle = this.config.hair;
    ctx.fillRect(-headW / 2 - 1, -headH - 2, headW + 2, 6);

    // Face features
    if (this.facing === 'front') {
      ctx.fillRect(-headW / 2, -headH, 4, headH - 2);
      ctx.fillRect(headW / 2 - 4, -headH, 4, headH - 2);
      ctx.fillStyle = '#111';
      ctx.fillRect(-4, -8, 2, 3);
      ctx.fillRect(2, -8, 2, 3);
      ctx.fillStyle = 'rgba(255,100,100,0.3)';
      ctx.fillRect(-6, -4, 3, 2);
      ctx.fillRect(3, -4, 3, 2);
    } else if (this.facing === 'back') {
      ctx.fillStyle = this.config.hair;
      ctx.fillRect(-headW / 2, -headH, headW, headH);
    } else if (this.facing === 'left') {
      ctx.fillRect(-headW / 2, -headH, headW - 4, headH);
      ctx.fillStyle = '#111';
      ctx.fillRect(-5, -8, 2, 3);
      ctx.fillStyle = '#ffceb4';
      ctx.fillRect(-9, -6, 2, 2);
    } else if (this.facing === 'right') {
      ctx.fillRect(-headW / 2 + 4, -headH, headW - 4, headH);
      ctx.fillStyle = '#111';
      ctx.fillRect(3, -8, 2, 3);
      ctx.fillStyle = '#ffceb4';
      ctx.fillRect(7, -6, 2, 2);
    }

    if (this.config.accessory === 'beret') {
      ctx.fillStyle = '#cf2a27';
      ctx.fillRect(-10, -headH - 4, 18, 5);
      ctx.fillStyle = '#111';
      ctx.fillRect(6, -headH - 6, 3, 3);
    } else if (this.config.accessory === 'glasses') {
      if (this.facing === 'front') {
        ctx.fillStyle = 'rgba(255,255,255,0.6)';
        ctx.fillRect(-6, -9, 5, 4);
        ctx.fillRect(1, -9, 5, 4);
        ctx.fillStyle = '#111';
        ctx.fillRect(-7, -10, 7, 1);
        ctx.fillRect(0, -10, 7, 1);
      }
    } else if (this.config.accessory === 'hair') {
      ctx.fillStyle = this.config.hair;
      if (this.facing === 'front' || this.facing === 'back') {
        ctx.fillRect(-headW / 2 - 2, -headH, 4, headH + 8);
        ctx.fillRect(headW / 2 - 2, -headH, 4, headH + 8);
      }
    } else if (this.config.accessory === 'pencil') {
      if (this.facing === 'front' || this.facing === 'right') {
        ctx.fillStyle = '#e5c07b';
        ctx.fillRect(6, 4, 10, 2);
        ctx.fillStyle = '#e06c75';
        ctx.fillRect(16, 4, 3, 2);
      }
    } else if (this.config.accessory === 'headphones') {
      ctx.fillStyle = '#1e1e24';
      ctx.fillRect(-headW / 2 - 2, -headH - 3, headW + 4, 3);
      if (this.facing !== 'back') {
        ctx.fillRect(-headW / 2 - 3, -8, 4, 8);
        ctx.fillRect(headW / 2 - 1, -8, 4, 8);
      }
    }

    if (this.speechBubble) {
      ctx.translate(0, -headH - 10);
      ctx.font = 'bold 12px "Noto Sans SC"';
      const padding = 8;
      const metrics = ctx.measureText(this.speechBubble);
      const w = metrics.width + padding * 2;
      const h = 24;

      ctx.fillStyle = 'rgba(0,0,0,0.2)';
      ctx.beginPath(); ctx.roundRect(-w / 2 + 2, -h + 2, w, h, 6); ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.beginPath(); ctx.roundRect(-w / 2, -h, w, h, 6); ctx.fill();

      ctx.beginPath();
      ctx.moveTo(-4, 0); ctx.lineTo(4, 0); ctx.lineTo(0, 5); ctx.fill();

      ctx.fillStyle = '#1e1e24';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(this.speechBubble, 0, -h / 2);
    }

    ctx.restore();
  }
}

// --- Environment Drawing Functions ---

function drawFloor(ctx, width, height, env, stars, clouds, rainDrops, windLines) {
  const horizonY = 140;
  const isDay = env === 'day_clear' || env === 'windy';
  const isRain = env === 'day_rain';
  const floorColor = isDay ? '#2b2c3d' : (isRain ? '#1f202e' : '#181825');
  const gridColor = isDay ? '#3b3c4d' : (isRain ? '#292a3b' : '#1e1e2e');
  const pillarColor = isDay ? '#313244' : (isRain ? '#252636' : '#1e1e2e');
  const pillarDark = isDay ? '#1e1e2e' : (isRain ? '#181825' : '#11111b');

  if (env === 'space') {
    ctx.fillStyle = '#050508';
    ctx.fillRect(0, 0, width, horizonY);
    const glow = ctx.createRadialGradient(width / 2, horizonY, 10, width / 2, horizonY, 400);
    glow.addColorStop(0, 'rgba(203,166,247,0.15)');
    glow.addColorStop(1, 'rgba(5,5,8,0)');
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, width, horizonY);
    stars.forEach((star) => {
      if (star.y > horizonY) return;
      star.alpha += star.speed;
      if (star.alpha > star.maxAlpha || star.alpha < 0.1) star.speed *= -1;
      ctx.globalAlpha = Math.max(0, Math.min(1, star.alpha));
      ctx.fillStyle = star.color;
      ctx.fillRect(star.x, star.y, star.size, star.size);
    });
    ctx.globalAlpha = 1;
    ctx.fillStyle = '#cba6f7';
    ctx.beginPath();
    ctx.arc(600, 60, 40, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.beginPath();
    ctx.arc(590, 65, 40, 0, Math.PI * 2);
    ctx.fill();
  } else if (env === 'day_clear' || env === 'windy') {
    const sky = ctx.createLinearGradient(0, 0, 0, horizonY);
    sky.addColorStop(0, env === 'windy' ? '#74b9ff' : '#0984e3');
    sky.addColorStop(1, env === 'windy' ? '#dfe6e9' : '#74b9ff');
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, width, horizonY);
    ctx.fillStyle = '#ffeaa7';
    ctx.beginPath();
    ctx.arc(150, 50, 25, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = 'rgba(255,234,167,0.3)';
    ctx.beginPath();
    ctx.arc(150, 50, 40, 0, Math.PI * 2);
    ctx.fill();
  } else if (env === 'day_rain') {
    const sky = ctx.createLinearGradient(0, 0, 0, horizonY);
    sky.addColorStop(0, '#2d3436');
    sky.addColorStop(1, '#636e72');
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, width, horizonY);
  } else {
    const sky = ctx.createLinearGradient(0, 0, 0, horizonY);
    sky.addColorStop(0, '#0a0a1a');
    sky.addColorStop(1, '#1a1b36');
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, width, horizonY);
    ctx.fillStyle = '#f5f6fa';
    ctx.beginPath();
    ctx.arc(650, 60, 20, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#0a0a1a';
    ctx.beginPath();
    ctx.arc(643, 55, 20, 0, Math.PI * 2);
    ctx.fill();
    stars.forEach((star) => {
      if (star.y > horizonY) return;
      star.alpha += star.speed;
      if (star.alpha > star.maxAlpha || star.alpha < 0.1) star.speed *= -1;
      ctx.globalAlpha = Math.max(0, Math.min(1, star.alpha));
      ctx.fillStyle = '#fff';
      ctx.fillRect(star.x, star.y, star.size, star.size);
    });
    ctx.globalAlpha = 1;
  }

  if (env !== 'space' && env !== 'night_clear') {
    ctx.fillStyle = env === 'day_rain' ? '#b2bec3' : '#ffffff';
    clouds.forEach((c) => {
      c.x += c.speed * (env === 'windy' ? 6 : 1);
      if (c.x > width + 100) c.x = -100;
      ctx.globalAlpha = 0.8;
      ctx.beginPath();
      ctx.arc(c.x, c.y, c.size, 0, Math.PI * 2);
      ctx.arc(c.x + c.size * 0.8, c.y - c.size * 0.4, c.size * 0.7, 0, Math.PI * 2);
      ctx.arc(c.x + c.size * 1.5, c.y, c.size * 0.8, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    });
  }

  if (env === 'day_rain') {
    rainDrops.forEach((r) => {
      r.y += r.speedY;
      r.x += r.speedX;
      if (r.y > horizonY) {
        r.y = rand(-50, 0);
        r.x = rand(0, width);
      }
      ctx.beginPath();
      ctx.moveTo(r.x, r.y);
      ctx.lineTo(r.x - r.speedX, r.y - r.speedY);
      ctx.strokeStyle = 'rgba(116,185,255,0.5)';
      ctx.lineWidth = 1;
      ctx.stroke();
    });
  }

  if (env === 'windy') {
    ctx.strokeStyle = 'rgba(255,255,255,0.4)';
    ctx.lineWidth = 2;
    windLines.forEach((line) => {
      line.x += line.speed;
      if (line.x > width + line.len) {
        line.x = -line.len;
        line.y = rand(20, horizonY - 20);
      }
      ctx.beginPath();
      ctx.moveTo(line.x, line.y);
      ctx.lineTo(line.x - line.len, line.y);
      ctx.stroke();
    });
  }

  if (env !== 'space') {
    ctx.fillStyle = (env === 'day_clear' || env === 'windy') ? '#718093' : '#2f3640';
    ctx.fillRect(50, horizonY - 30, 40, 30);
    ctx.fillRect(90, horizonY - 45, 30, 45);
    ctx.fillRect(450, horizonY - 50, 35, 50);
  }

  ctx.fillStyle = 'rgba(255,255,255,0.02)';
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(200, horizonY);
  ctx.lineTo(0, horizonY);
  ctx.fill();
  ctx.fillStyle = pillarColor;
  for (let i = 0; i <= width; i += 200) {
    ctx.fillRect(i - 6, 0, 12, horizonY);
    ctx.fillStyle = pillarDark;
    ctx.fillRect(i, 0, 6, horizonY);
    ctx.fillStyle = pillarColor;
  }

  ctx.fillStyle = pillarDark;
  ctx.fillRect(0, horizonY - 10, width, 10);
  ctx.fillStyle = '#09090b';
  ctx.fillRect(0, horizonY, width, 4);
  ctx.fillStyle = floorColor;
  ctx.fillRect(0, horizonY + 4, width, height - horizonY);
  ctx.fillStyle = gridColor;
  for (let i = horizonY + 4; i < height; i += 16) {
    ctx.fillRect(0, i, width, 1);
    for (let j = 0; j < width; j += 64) {
      const offset = i % 32 === 0 ? 0 : 32;
      ctx.fillRect(j + offset, i, 1, 16);
    }
  }

  const rx = 280;
  const ry = 480;
  const rw = 240;
  const rh = 100;
  ctx.fillStyle = isDay ? 'rgba(50,50,66,0.8)' : 'rgba(30,30,46,0.8)';
  ctx.beginPath();
  ctx.roundRect(rx, ry, rw, rh, 12);
  ctx.fill();
  ctx.strokeStyle = '#89b4fa';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(rx + 2, ry + 2, rw - 4, rh - 4, 10);
  ctx.stroke();
  ctx.fillStyle = 'rgba(203,166,247,0.7)';
  ctx.font = '10px "Press Start 2P"';
  ctx.textAlign = 'center';
  ctx.fillText('STAR LOUNGE', rx + rw / 2, ry + rh / 2 + 4);
}

function drawDeskBase(ctx, config, agent) {
  const dx = config.deskX;
  const dy = config.deskY;
  const deskW = 70;
  const deskH = 30;
  ctx.fillStyle = '#d08770';
  ctx.fillRect(dx - deskW / 2, dy - 15, deskW, deskH);
  ctx.fillStyle = '#bf616a';
  ctx.fillRect(dx - deskW / 2, dy + 15, deskW, 6);
  ctx.fillStyle = '#3b4252';
  ctx.fillRect(dx - deskW / 2 + 4, dy + 15, 4, 14);
  ctx.fillRect(dx + deskW / 2 - 8, dy + 15, 4, 14);
  ctx.fillStyle = '#eceff4';
  ctx.fillRect(dx + 20, dy - 5, 6, 8);
  ctx.fillStyle = '#5e81ac';
  ctx.fillRect(dx + 20, dy, 6, 2);
  if (config.name === '分镜师' || config.name === '分镜画师') {
    ctx.fillStyle = '#ebcb8b';
    ctx.fillRect(dx - 28, dy - 8, 14, 18);
    ctx.fillStyle = '#fff';
    ctx.fillRect(dx - 26, dy - 6, 10, 14);
  } else {
    drawPlant(ctx, dx - 32, dy - 18);
  }
  ctx.fillStyle = '#e5e9f0';
  ctx.fillRect(dx - 5, dy - 8, 10, 8);
  ctx.fillRect(dx - 15, dy - 10, 30, 4);
  ctx.fillStyle = '#2e3440';
  ctx.fillRect(dx - 18, dy - 30, 36, 24);
  if (agent && agent.state === 'working') {
    ctx.fillStyle = '#88c0d0';
    ctx.fillRect(dx - 16, dy - 28, 32, 20);
  } else {
    ctx.fillStyle = '#111';
    ctx.fillRect(dx - 16, dy - 28, 32, 20);
  }
  ctx.fillStyle = 'rgba(26,27,38,0.8)';
  ctx.beginPath();
  ctx.roundRect(dx - 25, dy + 25, 50, 14, 4);
  ctx.fill();
  ctx.fillStyle = config.color;
  ctx.font = 'bold 9px "Noto Sans SC"';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(config.name, dx, dy + 32);
}

function drawChair(ctx, config, agent) {
  const dx = config.deskX;
  const dy = config.deskY;
  const isOccupied = Boolean(agent && agent.state === 'working');
  const chairY = isOccupied ? dy + 8 : dy + 15;
  ctx.fillStyle = 'rgba(0,0,0,0.4)';
  ctx.beginPath();
  ctx.ellipse(dx, chairY + 8, 14, 5, 0, 0, Math.PI * 2);
  ctx.fill();
  if (!isOccupied) {
    ctx.fillStyle = '#4c566a';
    ctx.fillRect(dx - 12, chairY, 24, 6);
  }
  ctx.fillStyle = '#2e3440';
  ctx.fillRect(dx - 8, chairY + (isOccupied ? 2 : 6), 4, 8);
  ctx.fillRect(dx + 4, chairY + (isOccupied ? 2 : 6), 4, 8);
  ctx.fillStyle = '#434c5e';
  ctx.fillRect(dx - 10, chairY - 16, 20, 18);
  ctx.fillStyle = '#3b4252';
  ctx.fillRect(dx - 8, chairY - 14, 16, 14);
}

function drawDeskGlow(ctx, config) {
  const dx = config.deskX;
  const dy = config.deskY;
  ctx.save();
  ctx.globalCompositeOperation = 'screen';
  const gradient = ctx.createRadialGradient(dx, dy - 10, 10, dx, dy - 10, 40);
  gradient.addColorStop(0, 'rgba(136,192,208,0.4)');
  gradient.addColorStop(1, 'rgba(136,192,208,0)');
  ctx.fillStyle = gradient;
  ctx.beginPath();
  ctx.arc(dx, dy - 10, 40, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawPlant(ctx, x, y) {
  ctx.fillStyle = '#8fbcbb';
  ctx.fillRect(x, y, 16, 12);
  ctx.fillStyle = '#4c566a';
  ctx.fillRect(x, y + 8, 16, 4);

  ctx.fillStyle = '#a3be8c';
  ctx.beginPath(); ctx.arc(x + 8, y - 6, 10, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(x + 2, y - 2, 8, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(x + 14, y - 2, 8, 0, Math.PI * 2); ctx.fill();
}

function drawBookshelf(ctx, x, y, books) {
  ctx.fillStyle = '#5c3a21';
  ctx.fillRect(x, y - 80, 60, 80);
  ctx.fillStyle = '#8b5a2b';
  ctx.fillRect(x + 4, y - 76, 52, 72);
  ctx.fillStyle = '#5c3a21';
  ctx.fillRect(x + 4, y - 56, 52, 4);
  ctx.fillRect(x + 4, y - 36, 52, 4);
  ctx.fillRect(x + 4, y - 16, 52, 4);
  books.forEach((book) => {
    const shelfY = y - 76 + book.shelf * 20;
    ctx.fillStyle = book.color;
    ctx.fillRect(x + book.x, shelfY + 20 - book.height, book.width, book.height);
  });
}

function drawWaterDispenser(ctx, x, y) {
  ctx.fillStyle = '#eceff4';
  ctx.fillRect(x, y - 40, 24, 40);
  ctx.fillStyle = 'rgba(136,192,208,0.6)';
  ctx.beginPath();
  ctx.roundRect(x + 2, y - 65, 20, 25, 4);
  ctx.fill();
  ctx.fillStyle = 'rgba(94,129,172,0.8)';
  ctx.fillRect(x + 2, y - 55, 20, 15);
  ctx.fillStyle = '#d8dee9';
  ctx.fillRect(x + 2, y - 30, 20, 10);
  ctx.fillStyle = '#bf616a';
  ctx.fillRect(x + 4, y - 28, 4, 4);
  ctx.fillStyle = '#5e81ac';
  ctx.fillRect(x + 16, y - 28, 4, 4);
}

function drawSofa(ctx, x, y) {
  ctx.fillStyle = '#5e81ac';
  ctx.beginPath();
  ctx.roundRect(x, y - 30, 80, 20, 4);
  ctx.fill();
  ctx.fillStyle = '#81a1c1';
  ctx.beginPath();
  ctx.roundRect(x, y - 15, 80, 15, 2);
  ctx.fill();
  ctx.fillStyle = '#4c566a';
  ctx.fillRect(x - 5, y - 20, 10, 20);
  ctx.fillRect(x + 75, y - 20, 10, 20);
  ctx.fillStyle = '#2e3440';
  ctx.fillRect(x, y, 6, 4);
  ctx.fillRect(x + 74, y, 6, 4);
}

function drawDoll(ctx, x, y) {
  ctx.fillStyle = '#bf616a';
  ctx.beginPath();
  ctx.arc(x, y - 10, 8, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(x - 6, y - 14, 4, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(x + 6, y - 14, 4, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#d08770';
  ctx.beginPath();
  ctx.ellipse(x, y, 8, 10, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#eceff4';
  ctx.beginPath();
  ctx.arc(x, y - 9, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#2e3440';
  ctx.fillRect(x - 2, y - 10, 1, 2);
  ctx.fillRect(x + 1, y - 10, 1, 2);
}

// --- Main Component ---

export default function AgentOfficeBoard({ snapshot, onQuickCommand }) {
  const project = snapshot;
  const canvasRef = useRef(null);
  const logContainerRef = useRef(null);
  const [logs, setLogs] = useState([]);
  const [envMode, setEnvMode] = useState('space');
  const actionTimerRef = useRef(null);
  const engineRef = useRef({
    agents: [],
    particles: [],
    lastTime: 0,
    officeState: 'IDLE',
    currentEnv: 'space',
    bgStars: [],
    envClouds: [],
    rainDrops: [],
    windLines: [],
    bookshelfBooks: []
  });
  const addLogRef = useRef(null);

  const addLog = (msg, color = '#abb2bf') => {
    const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    setLogs((prev) => [...prev.slice(-59), { time, msg, color }]);
  };

  addLogRef.current = addLog;

  const agentStates = useMemo(() => {
    const states = {};
    Object.keys(ROLE_MAPPING).forEach((nodeName) => {
      const status = resolveNodeStatus(project, nodeName);
      const isWorking = status === 'running' || status === 'working' || status === 'review';
      states[nodeName] = isWorking ? 'working' : 'wander';
    });
    return states;
  }, [project]);

  useEffect(() => {
    const engine = engineRef.current;
    const newAgents = [];
    newAgents.push(new Agent('director', DIRECTOR_CONFIG));
    Object.keys(ROLE_MAPPING).forEach((nodeName) => {
      newAgents.push(new Agent(nodeName, ROLE_MAPPING[nodeName]));
    });
    engine.agents = newAgents;
    engine.bgStars = Array.from({ length: 200 }, () => ({
      x: rand(0, 800),
      y: rand(0, 600),
      size: Math.random() < 0.9 ? 1 : 2,
      alpha: rand(0.1, 0.8),
      maxAlpha: rand(0.5, 1),
      speed: rand(0.005, 0.02) * (Math.random() < 0.5 ? 1 : -1),
      color: Math.random() < 0.8 ? '#ffffff' : (Math.random() < 0.5 ? '#89b4fa' : '#f9e2af')
    }));
    engine.envClouds = Array.from({ length: 6 }, () => ({
      x: rand(0, 800),
      y: rand(10, 80),
      size: rand(15, 30),
      speed: rand(0.1, 0.3)
    }));
    engine.rainDrops = Array.from({ length: 100 }, () => ({
      x: rand(0, 800),
      y: rand(0, 140),
      speedY: rand(4, 8),
      speedX: rand(1, 2)
    }));
    engine.windLines = Array.from({ length: 15 }, () => ({
      x: rand(0, 800),
      y: rand(20, 120),
      len: rand(20, 80),
      speed: rand(10, 20)
    }));
    engine.bookshelfBooks = createBookshelfBooks();
    addLog('系统初始化完毕。星空主题已加载。', '#cba6f7');
    addLog('团队当前处于 [休息/待机] 状态。', '#81a1c1');
    return () => {
      if (actionTimerRef.current) {
        window.clearTimeout(actionTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const engine = engineRef.current;
    let hasWorking = false;
    engine.agents.forEach((agent) => {
      if (agent.id === 'director') return;
      const desired = agentStates[agent.id];
      if (desired) {
        agent.desiredState = desired;
        if (desired === 'working') {
          hasWorking = true;
        }
      }
    });
    const director = engine.agents.find((item) => item.id === 'director');
    if (director) {
      director.desiredState = hasWorking ? 'working' : 'wander';
    }
  }, [agentStates]);

  useEffect(() => {
    const container = logContainerRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, [logs]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    let animationFrameId;
    const loop = (timestamp) => {
      const engine = engineRef.current;
      if (!engine.lastTime) engine.lastTime = timestamp;
      const dt = timestamp - engine.lastTime;
      const safeDt = Math.min(dt, 50);
      engine.particles.forEach(p => p.update());
      engine.particles = engine.particles.filter(p => p.life > 0);

      drawFloor(
        ctx,
        canvas.width,
        canvas.height,
        engine.currentEnv,
        engine.bgStars,
        engine.envClouds,
        engine.rainDrops,
        engine.windLines
      );

      const renderList = [];
      renderList.push({ type: 'bookshelf', y: 220, x: 80 });
      renderList.push({ type: 'water_dispenser', y: 220, x: 720 });
      renderList.push({ type: 'sofa', y: 540, x: 400 });
      renderList.push({ type: 'doll', y: 541, x: 420, onSofa: true });
      renderList.push({ type: 'plant', y: 500, x: 700 });
      renderList.push({ type: 'plant', y: 550, x: 50 });

      [DIRECTOR_CONFIG, ...Object.values(ROLE_MAPPING)].forEach((config) => {
        renderList.push({ type: 'desk_base', y: config.deskY, config });
        renderList.push({ type: 'chair', y: config.deskY + 14, config });
        renderList.push({ type: 'desk_glow', y: config.deskY + 100, config });
      });
      engine.agents.forEach((agent) => {
        renderList.push({ type: 'agent', y: agent.y, agent });
      });
      renderList.sort((a, b) => a.y - b.y);

      renderList.forEach((item) => {
        if (item.type === 'agent') {
          const effects = item.agent.update(safeDt, item.agent.desiredState || 'wander');
          if (effects.enteredWorking && addLogRef.current) {
            addLogRef.current(`${item.agent.config.name} 就位，${item.agent.config.action}`, item.agent.config.color);
          }
          if (effects.spawnWorkParticle) {
            engine.particles.push(new Particle(item.agent.x + rand(-10, 10), item.agent.y - 30, 'work', item.agent.config.color));
          }
          if (effects.spawnIdeaParticle) {
            engine.particles.push(new Particle(item.agent.x, item.agent.y - 40, 'idea', '#e5c07b'));
          }
          if (effects.spawnZzzParticle) {
            engine.particles.push(new Particle(item.agent.x + 10, item.agent.y - 30, 'zzz', '#565f89'));
          }
          item.agent.draw(ctx);
          return;
        }
        const owner = engine.agents.find((agent) => agent.config === item.config);
        if (item.type === 'desk_base') {
          drawDeskBase(ctx, item.config, owner);
        } else if (item.type === 'chair') {
          drawChair(ctx, item.config, owner);
        } else if (item.type === 'desk_glow' && owner?.state === 'working') {
          drawDeskGlow(ctx, item.config);
        } else if (item.type === 'bookshelf') {
          drawBookshelf(ctx, item.x, item.y, engine.bookshelfBooks);
        } else if (item.type === 'water_dispenser') {
          drawWaterDispenser(ctx, item.x, item.y);
        } else if (item.type === 'sofa') {
          drawSofa(ctx, item.x, item.y);
        } else if (item.type === 'doll') {
          drawDoll(ctx, item.x, item.onSofa ? item.y - 15 : item.y);
        } else if (item.type === 'plant') {
          drawPlant(ctx, item.x, item.y);
        }
      });

      engine.particles.forEach((p) => p.draw(ctx));
      const vignette = ctx.createRadialGradient(canvas.width / 2, canvas.height / 2, canvas.height / 3, canvas.width / 2, canvas.height / 2, canvas.width);
      vignette.addColorStop(0, 'rgba(0,0,0,0)');
      vignette.addColorStop(1, 'rgba(0,0,0,0.6)');
      ctx.fillStyle = vignette;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      if (engine.currentEnv === 'day_rain') {
        ctx.fillStyle = 'rgba(45,52,54,0.15)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }

      engine.lastTime = timestamp;
      animationFrameId = window.requestAnimationFrame(loop);
    };
    
    animationFrameId = window.requestAnimationFrame(loop);
    
    return () => window.cancelAnimationFrame(animationFrameId);
  }, []);

  const handleEnvChange = (value) => {
    setEnvMode(value);
    engineRef.current.currentEnv = value;
    addLog(`【环境变更】已切换至 ${ENV_LABELS[value]}`, '#a29bfe');
  };

  const handleAction = () => {
    const engine = engineRef.current;
    if (engine.officeState === 'WORKING') {
      return;
    }
    engine.officeState = 'MEETING';
    addLog('【Action】指令下达，开始分配任务...', '#e06c75');
    const director = engine.agents.find((agent) => agent.id === 'director');
    if (director) {
      director.desiredState = 'working';
      director.state = 'going_to_desk';
      director.targetX = director.config.deskX;
      director.targetY = director.config.deskY + 8;
      director.say('各就各位，新项目启动！', 3500);
    }
    engine.agents.forEach((agent) => {
      if (agent.id !== 'director') {
        engine.particles.push(new Particle(agent.x, agent.y - 40, 'idea', '#e5c07b'));
        agent.facing = director && director.x > agent.x ? 'right' : 'left';
      }
    });
    if (actionTimerRef.current) {
      window.clearTimeout(actionTimerRef.current);
    }
    actionTimerRef.current = window.setTimeout(() => {
      engine.officeState = 'WORKING';
      engine.agents.forEach((agent) => {
        if (agent.id !== 'director') {
          agent.desiredState = 'working';
          agent.say('收到！', 1800);
        }
      });
      addLog('团队已进入 [工作/产出] 状态。', '#61afef');
    }, 1200);
    if (onQuickCommand) {
      onQuickCommand('开始下一阶段');
    }
  };

  const handleRest = () => {
    const engine = engineRef.current;
    if (engine.officeState === 'IDLE') {
      return;
    }
    engine.officeState = 'IDLE';
    addLog('【Rest】进入休息时间，恢复体力。', '#c678dd');
    const director = engine.agents.find((agent) => agent.id === 'director');
    if (director) {
      director.say('进度不错，大家休息一下吧。', 3000);
    }
    engine.agents.forEach((agent) => {
      agent.desiredState = 'wander';
      agent.state = 'wander';
      agent.targetX = rand(LOUNGE_AREA.minX, LOUNGE_AREA.maxX);
      agent.targetY = rand(LOUNGE_AREA.minY, LOUNGE_AREA.maxY);
    });
    if (actionTimerRef.current) {
      window.clearTimeout(actionTimerRef.current);
    }
    if (onQuickCommand) {
      onQuickCommand('暂停');
    }
  };

  return (
    <div className="agent-office-board">
       <div className="canvas-container">
          <canvas 
            ref={canvasRef} 
            width={800} 
            height={600} 
            className="pixel-canvas" 
          />
          <div className="crt-overlay" />
       </div>
       
       <div className="glass-panel">
          <div className="glass-header">
             <h1 className="glass-title">PIXEL<br/>STUDIO</h1>
             <p className="glass-subtitle">AI Agent 协同工作站 v2.0</p>
          </div>
          
          <div className="glass-controls">
             <button className="pixel-btn pixel-btn-action" onClick={handleAction}>
               <span>▶</span> 导演喊Action!
             </button>
             <button className="pixel-btn pixel-btn-rest" onClick={handleRest}>
               <span>☕</span> 宣布休息
             </button>
          </div>

          <div className="glass-env">
            <h3 className="glass-env-title">环境控制 / ENV</h3>
            <select className="glass-env-select" value={envMode} onChange={(event) => handleEnvChange(event.target.value)}>
              <option value="space">🌌 宇宙星空 (Space)</option>
              <option value="day_clear">☀️ 晴朗白天 (Day Clear)</option>
              <option value="day_rain">🌧️ 阴雨绵绵 (Rainy)</option>
              <option value="night_clear">🌙 繁星都市 (Night)</option>
              <option value="windy">🍃 疾风掠过 (Windy)</option>
            </select>
          </div>
          
          <div className="glass-log">
             <h2 className="log-title">活动日志 / LOG</h2>
             <div className="log-container" ref={logContainerRef}>
                {logs.map((log, i) => (
                  <div key={i} className="log-entry" style={{ borderColor: log.color || '#abb2bf' }}>
                    <span className="log-time">[{log.time}]</span> <span style={{ color: log.color || '#abb2bf' }}>{log.msg}</span>
                  </div>
                ))}
             </div>
          </div>
       </div>
    </div>
  );
}
