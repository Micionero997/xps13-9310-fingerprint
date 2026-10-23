// Offline SIGFM evaluation for goodix53xd.
//
// Each input is a raw dump (64x80 frame then background, host-endian u16)
// prefixed with a label: "label:path". Images are built like build_image()
// in goodix53xd.c (background subtraction, stretch, 2x upscale). For every
// probe, the score is the best one against all other frames of the template
// label, which is how libfprint verifies against a multi-print template.
//
// Usage: sigfm-eval <template-label> label:frame.bin...
// Output: one line per probe "probe-label score", plus keypoint counts.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

#include "sigfm.hpp"

namespace {
constexpr int W = 64, H = 80, N = W * H;
// Variant knobs for experiments (environment): SCALE, NORM_RADIUS (0 = off)
int SCALE = 2, NORM_RADIUS = 0;

std::vector<unsigned char> build(const std::vector<uint16_t>& raw)
{
    const uint16_t* frame = raw.data();
    const uint16_t* bg = raw.data() + N;
    std::vector<int> depth(N);
    for (int i = 0; i < N; i++)
        depth[i] = std::max(0, int(bg[i]) - int(frame[i]));

    if (NORM_RADIUS > 0) {
        // Local contrast normalization: (v - local mean) / local stddev
        const int r = NORM_RADIUS;
        std::vector<int> out(N);
        for (int y = 0; y < H; y++)
            for (int x = 0; x < W; x++) {
                double s = 0, s2 = 0;
                int n = 0;
                for (int yy = std::max(0, y - r); yy <= std::min(H - 1, y + r); yy++)
                    for (int xx = std::max(0, x - r); xx <= std::min(W - 1, x + r); xx++) {
                        double v = depth[yy * W + xx];
                        s += v;
                        s2 += v * v;
                        n++;
                    }
                double mean = s / n, sd = std::sqrt(std::max(1.0, s2 / n - mean * mean));
                out[y * W + x] = int(1000 * (depth[y * W + x] - mean) / sd);
            }
        depth = out;
    }
    std::vector<int> sorted = depth;
    std::sort(sorted.begin(), sorted.end());
    int lo = sorted[N / 100], hi = sorted[N - 1 - N / 100];
    if (hi <= lo)
        hi = lo + 1;

    std::vector<unsigned char> small(N);
    for (int i = 0; i < N; i++) {
        int d = std::clamp(depth[i], lo, hi);
        small[i] = 255 - (d - lo) * 255 / (hi - lo);
    }

    const int w = W * SCALE, h = H * SCALE;
    std::vector<unsigned char> img(w * h);
    for (int y = 0; y < h; y++) {
        double sy = std::clamp((y + 0.5) / SCALE - 0.5, 0.0, double(H - 1));
        int y0 = int(sy), y1 = std::min(y0 + 1, H - 1);
        double fy = sy - y0;
        for (int x = 0; x < w; x++) {
            double sx = std::clamp((x + 0.5) / SCALE - 0.5, 0.0, double(W - 1));
            int x0 = int(sx), x1 = std::min(x0 + 1, W - 1);
            double fx = sx - x0;
            double t = small[y0 * W + x0] * (1 - fx) + small[y0 * W + x1] * fx;
            double b = small[y1 * W + x0] * (1 - fx) + small[y1 * W + x1] * fx;
            img[y * w + x] = (unsigned char)(t * (1 - fy) + b * fy + 0.5);
        }
    }
    return img;
}

struct Sample {
    std::string label;
    SigfmImgInfo* info;
};
} // namespace

int main(int argc, char** argv)
{
    if (argc < 3) {
        std::fprintf(stderr, "usage: %s template-label label:frame.bin...\n", argv[0]);
        return 1;
    }
    const std::string tmpl = argv[1];
    if (getenv("SCALE"))
        SCALE = atoi(getenv("SCALE"));
    if (getenv("NORM_RADIUS"))
        NORM_RADIUS = atoi(getenv("NORM_RADIUS"));
    std::vector<Sample> samples;

    for (int a = 2; a < argc; a++) {
        std::string arg = argv[a];
        auto colon = arg.find(':');
        std::ifstream in(arg.substr(colon + 1), std::ios::binary);
        std::vector<char> bytes{std::istreambuf_iterator<char>(in), {}};
        if (bytes.size() != 2 * N * sizeof(uint16_t))
            continue;
        std::vector<uint16_t> raw(2 * N);
        std::memcpy(raw.data(), bytes.data(), bytes.size());
        auto img = build(raw);
        if (getenv("DUMP_IMG") && samples.empty()) {
            // Debug: raw 8-bit image of the first sample, to diff with the driver
            std::ofstream(getenv("DUMP_IMG"), std::ios::binary)
                .write(reinterpret_cast<const char*>(img.data()), img.size());
        }
        SigfmImgInfo* info = sigfm_extract(img.data(), W * SCALE, H * SCALE);
        std::printf("keypoints %s %d\n", arg.substr(0, colon).c_str(),
                    sigfm_keypoints_count(info));
        samples.push_back({arg.substr(0, colon), info});
    }

    for (std::size_t p = 0; p < samples.size(); p++) {
        int best = 0;
        for (std::size_t t = 0; t < samples.size(); t++) {
            if (t == p || samples[t].label != tmpl)
                continue;
            best = std::max(best, sigfm_match_score(samples[p].info, samples[t].info));
        }
        std::printf("score %s %d\n", samples[p].label.c_str(), best);
    }
    return 0;
}
