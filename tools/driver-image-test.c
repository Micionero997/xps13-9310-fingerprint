/* Run goodix53xd.c's build_image() on one raw dump and write the 8-bit
 * result, to check it matches tools/sigfm-eval byte for byte. */
#include "drivers/goodixtls/goodix53xd.c"

int
main (int argc, char **argv)
{
  g_autofree guint16 *buf = NULL;
  gsize len;

  if (argc != 3 || !g_file_get_contents (argv[1], (gchar **) &buf, &len, NULL) ||
      len != 2 * GOODIX53XD_FRAME_SIZE * sizeof (guint16))
    return 1;
  g_autoptr(FpImage) img = build_image (buf, buf + GOODIX53XD_FRAME_SIZE);
  return g_file_set_contents (argv[2], (gchar *) img->data,
                              img->width * img->height, NULL) ? 0 : 1;
}
