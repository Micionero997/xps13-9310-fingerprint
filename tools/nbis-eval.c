/*
 * Offline evaluation of goodix53xd image processing with libfprint's NBIS.
 *
 * Reads raw dumps written by the driver (FP_GOODIX53XD_DUMP: 64x80 frame then
 * background, host-endian u16) and, for each processing variant, reports how
 * many frames yield minutiae and the bozorth3 scores between frames of the
 * same finger (each frame matched against all the others).
 *
 * Usage: nbis-eval <scale> <partial 0|1> <local-norm 0|1> frame.bin...
 */
#include <glib.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "fpi-image.h"
#include "fpi-print.h"
#include "fp-print-private.h"

#define W 64
#define H 80
#define N (W * H)

static int
depth (const guint16 *frame, const guint16 *bg, int i)
{
  return MAX (0, (int) bg[i] - (int) frame[i]);
}

/* Same steps as build_image() in goodix53xd.c, plus optional local
 * normalization (zero mean, unit variance over a sliding window) */
static FpImage *
build (const guint16 *frame, const guint16 *bg, int scale, gboolean partial,
       gboolean local_norm)
{
  gdouble val[N];
  guint8 small[N];
  int w = W * scale, h = H * scale;
  FpImage *img;

  for (int i = 0; i < N; i++)
    val[i] = depth (frame, bg, i);

  if (local_norm)
    {
      const int r = 6;
      gdouble out[N];

      for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++)
          {
            gdouble s = 0, s2 = 0;
            int n = 0;
            for (int yy = MAX (0, y - r); yy <= MIN (H - 1, y + r); yy++)
              for (int xx = MAX (0, x - r); xx <= MIN (W - 1, x + r); xx++)
                {
                  s += val[yy * W + xx];
                  s2 += val[yy * W + xx] * val[yy * W + xx];
                  n++;
                }
            gdouble mean = s / n, sd = sqrt (MAX (1, s2 / n - mean * mean));
            out[y * W + x] = (val[y * W + x] - mean) / sd;
          }
      memcpy (val, out, sizeof (val));
    }

  gdouble sorted[N];
  memcpy (sorted, val, sizeof (sorted));
  int cmp (const void *a, const void *b)
  {
    gdouble d = *(const gdouble *) a - *(const gdouble *) b;
    return (d > 0) - (d < 0);
  }
  qsort (sorted, N, sizeof (gdouble), cmp);
  gdouble lo = sorted[N / 100], hi = sorted[N - 1 - N / 100];
  if (hi <= lo)
    hi = lo + 1;
  for (int i = 0; i < N; i++)
    small[i] = 255 - (guint8) (CLAMP ((val[i] - lo) / (hi - lo), 0, 1) * 255);

  img = fp_image_new (w, h);
  if (partial)
    img->flags |= FPI_IMAGE_PARTIAL;
  for (int y = 0; y < h; y++)
    {
      gdouble sy = CLAMP ((y + 0.5) / scale - 0.5, 0, H - 1);
      int y0 = (int) sy, y1 = MIN (y0 + 1, H - 1);
      gdouble fy = sy - y0;
      for (int x = 0; x < w; x++)
        {
          gdouble sx = CLAMP ((x + 0.5) / scale - 0.5, 0, W - 1);
          int x0 = (int) sx, x1 = MIN (x0 + 1, W - 1);
          gdouble fx = sx - x0;
          gdouble t = small[y0 * W + x0] * (1 - fx) + small[y0 * W + x1] * fx;
          gdouble b = small[y1 * W + x0] * (1 - fx) + small[y1 * W + x1] * fx;
          img->data[y * w + x] = (guint8) (t * (1 - fy) + b * fy + 0.5);
        }
    }
  return img;
}

static GMainLoop *loop;

static void
on_minutiae (GObject *img, GAsyncResult *res, gpointer user_data)
{
  g_autoptr(GError) error = NULL;

  fp_image_detect_minutiae_finish (FP_IMAGE (img), res, &error);
  g_main_loop_quit (loop);
}

static FpPrint *
print_from (FpImage *img)
{
  FpPrint *print = g_object_new (FP_TYPE_PRINT, "driver", "goodixtls53xd",
                                 "device-id", "eval", NULL);

  fpi_print_set_type (print, FPI_PRINT_NBIS);
  fp_image_detect_minutiae (img, NULL, on_minutiae, NULL);
  g_main_loop_run (loop);
  if (!fpi_print_add_from_image (print, img, NULL))
    g_clear_object (&print);
  return print;
}

int
main (int argc, char **argv)
{
  if (argc < 5)
    {
      fprintf (stderr, "usage: %s scale partial local-norm frame.bin...\n", argv[0]);
      return 1;
    }
  int scale = atoi (argv[1]);
  gboolean partial = atoi (argv[2]), local_norm = atoi (argv[3]);
  int nframes = argc - 4, ok = 0;
  FpPrint **prints = g_new0 (FpPrint *, nframes);
  GArray *scores = g_array_new (FALSE, FALSE, sizeof (int));

  loop = g_main_loop_new (NULL, FALSE);

  for (int f = 0; f < nframes; f++)
    {
      g_autofree guint16 *buf = NULL;
      gsize len;

      if (!g_file_get_contents (argv[4 + f], (gchar **) &buf, &len, NULL) ||
          len != 2 * N * sizeof (guint16))
        continue;
      g_autoptr(FpImage) img = build (buf, buf + N, scale, partial, local_norm);
      prints[f] = print_from (img);
      if (prints[f])
        {
          GPtrArray *m = fp_image_get_minutiae (img);
          printf ("%s: %u minutiae\n", argv[4 + f], m ? m->len : 0);
          ok++;
        }
    }

  /* Each frame against every other frame: genuine score distribution */
  for (int a = 0; a < nframes; a++)
    for (int b = 0; b < nframes; b++)
      {
        if (a == b || !prints[a] || !prints[b])
          continue;
        struct xyt_struct *pa = g_ptr_array_index (prints[a]->prints, 0);
        struct xyt_struct *pb = g_ptr_array_index (prints[b]->prints, 0);
        int probe_len = bozorth_probe_init (pa);
        int s = bozorth_to_gallery (probe_len, pa, pb);
        g_array_append_val (scores, s);
      }

  int above[4] = { 0 }, thr[4] = { 10, 16, 24, 40 }, max = 0;
  for (guint i = 0; i < scores->len; i++)
    {
      int s = g_array_index (scores, int, i);
      max = MAX (max, s);
      for (int t = 0; t < 4; t++)
        if (s >= thr[t])
          above[t]++;
    }
  printf ("SUMMARY scale=%d partial=%d localnorm=%d: minutiae ok %d/%d, "
          "pairs %u, max %d, >=10 %d, >=16 %d, >=24 %d, >=40 %d\n",
          scale, partial, local_norm, ok, nframes, scores->len, max,
          above[0], above[1], above[2], above[3]);
  return 0;
}
