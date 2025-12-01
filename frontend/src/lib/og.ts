const googleFontCss = 'https://fonts.googleapis.com/css2?family=Press+Start+2P&text=SnakeBenchMatchupvs0123456789';

const pressStartFontPromise = fetch(googleFontCss, { cache: 'force-cache' })
  .then(async (res) => {
    if (!res.ok) return null;
    const css = await res.text();
    const fontUrl = css.match(/src: url\((https:[^)]*)\) format\('woff2'\)/)?.[1];
    if (!fontUrl) return null;

    const fontRes = await fetch(fontUrl, { cache: 'force-cache' });
    if (!fontRes.ok) return null;
    return fontRes.arrayBuffer();
  })
  .catch(() => null);

const sourceSansFontPromise = fetch(
  new URL('../../public/fonts/Source_Sans_3/static/SourceSans3-SemiBold.ttf', import.meta.url)
)
  .then((res) => res.arrayBuffer())
  .catch(() => null);

type OgFont = {
  name: string;
  data: ArrayBuffer;
  style: 'normal' | 'italic';
  weight: 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900;
};

export async function getOgFonts(): Promise<OgFont[]> {
  const [pressStart, sourceSans] = await Promise.all([
    pressStartFontPromise,
    sourceSansFontPromise,
  ]);

  const fonts: OgFont[] = [];

  if (pressStart) {
    fonts.push({
      name: 'Press Start 2P',
      data: pressStart,
      style: 'normal',
      weight: 400,
    });
  }

  if (sourceSans) {
    fonts.push({
      name: 'Source Sans 3',
      data: sourceSans,
      style: 'normal',
      weight: 700,
    });
  }

  return fonts;
}
