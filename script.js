// Canvas‑based animated wire‑frame grid
const canvas = document.getElementById('grid-canvas');
const ctx = canvas.getContext('2d');
let w, h;
let offsetX = 0, offsetY = 0;
const speed = 0.2; // drift speed (px per frame)

function resize(){
  w = canvas.width = window.innerWidth;
  h = canvas.height = window.innerHeight;
}
window.addEventListener('resize', resize);
resize();

function draw(){
  ctx.clearRect(0,0,w,h);
  ctx.strokeStyle = 'rgba(70,120,200,0.15)';
  ctx.lineWidth = 1;
  const spacing = 60; // distance between lines
  const startX = -spacing + (offsetX % spacing);
  const startY = -spacing + (offsetY % spacing);
  // vertical lines
  for(let x=startX; x<w; x+=spacing){
    ctx.beginPath();
    ctx.moveTo(x,0);
    ctx.lineTo(x,h);
    ctx.stroke();
  }
  // horizontal lines
  for(let y=startY; y<h; y+=spacing){
    ctx.beginPath();
    ctx.moveTo(0,y);
    ctx.lineTo(w,y);
    ctx.stroke();
  }
  // drift
  offsetX += speed;
  offsetY += speed*0.6;
  requestAnimationFrame(draw);
}

draw();