// Render local, poster legível no primeiro quadro e MP4 pronto para o site.
import { spawnSync } from 'node:child_process';
import { mkdirSync, renameSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const dir = path.dirname(fileURLToPath(import.meta.url));
const tmp = path.join(dir, '.render-tmp');
mkdirSync(tmp, { recursive: true });
const hyperframes = process.env.HYPERFRAMES_BIN || path.join(dir, 'node_modules/.bin/hyperframes');
const ffmpeg = process.env.HYPERFRAMES_FFMPEG_PATH || 'ffmpeg';
const ffprobe = process.env.HYPERFRAMES_FFPROBE_PATH || 'ffprobe';

function run(binary, args, capture = false) {
  const result = spawnSync(binary, args, {
    cwd: dir,
    env: { ...process.env, HYPERFRAMES_NO_TELEMETRY: '1' },
    stdio: capture ? ['ignore', 'pipe', 'inherit'] : 'inherit',
    encoding: 'utf8',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${binary} terminou com código ${result.status}`);
  return result.stdout;
}

run(hyperframes, ['check', 'composition']);
run(hyperframes, ['render', 'composition', '--fps', '30', '--quality', 'delivery',
  '--workers', '2', '--output', path.join(tmp, 'render.mp4')]);

// Dashboard plenamente visível: a capa apresenta o produto em uso.
run(ffmpeg, ['-hide_banner', '-loglevel', 'error', '-y', '-ss', '5.4',
  '-i', path.join(tmp, 'render.mp4'), '-frames:v', '1', '-q:v', '2', 'brag.jpg']);
run(ffmpeg, ['-hide_banner', '-loglevel', 'error', '-y',
  '-i', path.join(tmp, 'render.mp4'), '-i', 'brag.jpg',
  '-filter_complex', "[0:v][1:v]overlay=0:0:enable='eq(n,0)'[v]",
  '-map', '[v]', '-map', '0:a:0', '-c:v', 'libx264', '-crf', '20',
  '-preset', 'slow', '-pix_fmt', 'yuv420p', '-c:a', 'copy',
  '-movflags', '+faststart', path.join(tmp, 'site.mp4')]);

const info = JSON.parse(run(ffprobe, ['-v', 'error', '-show_format', '-show_streams',
  '-of', 'json', path.join(tmp, 'site.mp4')], true));
const video = info.streams.find(s => s.codec_type === 'video');
const audio = info.streams.find(s => s.codec_type === 'audio');
if (!video || !audio || video.width !== 1920 || video.height !== 1080 ||
    Math.abs(Number(info.format.duration) - 25) > 0.1 || video.pix_fmt !== 'yuv420p') {
  throw new Error('O arquivo não atende ao contrato de entrega (1080p, 25 s, áudio e yuv420p).');
}
renameSync(path.join(tmp, 'site.mp4'), path.join(dir, 'brag.mp4'));
console.log('Pronto: brag.mp4 e brag.jpg — 25 s, 1080p, H.264/AAC.');
