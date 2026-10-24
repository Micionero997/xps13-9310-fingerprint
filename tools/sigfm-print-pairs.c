/*
 * Print the SIGFM score between every pair of samples in an enrolled print.
 * High scores mean two enroll touches covered the same part of the finger.
 * Reads a print file written by fprintd (/var/lib/fprint/<user>/...), so it
 * needs root, but prints only scores and keypoint counts.
 *
 * Build after scripts/build-libfprint.sh (see tools/README.md):
 *   L=work/libfprint
 *   gcc -O2 -o work/sigfm-print-pairs tools/sigfm-print-pairs.c \
 *     -I$L/build -I$L/libfprint -I$L/build/libfprint \
 *     -I$L/libfprint/nbis/include -I$L/libfprint/nbis/libfprint-include \
 *     $(pkg-config --cflags glib-2.0 gusb) \
 *     $L/build/libfprint/sigfm/libsigfm.a -L$L/build/libfprint -lfprint-2 \
 *     -Wl,-rpath,$PWD/$L/build/libfprint \
 *     $(pkg-config --libs glib-2.0 gobject-2.0) -lopencv_features2d -lopencv_core -lstdc++ -lm
 *
 * Usage: sudo work/sigfm-print-pairs /var/lib/fprint/<user>/goodixtls53xd/<id>/7
 * (7 is the right index finger, see FpFinger)
 */

#include <stdio.h>

#include "fp-print-private.h"
#include "sigfm/sigfm.hpp"

int
main (int argc, char **argv)
{
  if (argc != 2)
    {
      fprintf (stderr, "usage: %s <print file>\n", argv[0]);
      return 2;
    }

  gchar *data = NULL;
  gsize len = 0;
  GError *error = NULL;

  if (!g_file_get_contents (argv[1], &data, &len, &error))
    {
      fprintf (stderr, "%s\n", error->message);
      return 1;
    }

  FpPrint *print = fp_print_deserialize ((guchar *) data, len, &error);
  if (!print)
    {
      fprintf (stderr, "%s\n", error->message);
      return 1;
    }
  if (print->type != FPI_PRINT_SIGFM)
    {
      fprintf (stderr, "not a SIGFM print\n");
      return 1;
    }

  const guint n = print->prints->len;
  SigfmImgInfo **s = g_new (SigfmImgInfo *, n);
  for (guint i = 0; i < n; i++)
    s[i] = (SigfmImgInfo *) g_ptr_array_index (print->prints, i);

  printf ("%u samples\nkeypoints:", n);
  for (guint i = 0; i < n; i++)
    printf (" %d", sigfm_keypoints_count (s[i]));
  printf ("\n\nscore row->column (probe row against enrolled column)\n    ");
  for (guint j = 0; j < n; j++)
    printf ("%6u", j);
  printf ("\n");

  for (guint i = 0; i < n; i++)
    {
      int best = 0;
      printf ("%3u ", i);
      for (guint j = 0; j < n; j++)
        {
          if (i == j)
            {
              printf ("%6s", "-");
              continue;
            }
          int score = sigfm_match_score (s[i], s[j]);
          if (score > best)
            best = score;
          printf ("%6d", score);
        }
      printf ("   best %d\n", best);
    }

  g_free (s);
  g_object_unref (print);
  g_free (data);
  return 0;
}
