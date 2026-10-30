#include <stddef.h>
#include <stdint.h>

/* Volatile reads retain the actual strided loads and scalar reduction. */
double stride_sum(const double *data, size_t n, size_t stride) {
    const volatile double *a = data;
    double total = 0.0;
    for (size_t i = 0; i < n; i += stride) total += a[i];
    return total;
}

void matmul_ijk(const double *a, const double *b, double *c, size_t n) {
    for (size_t i = 0; i < n; ++i)
        for (size_t j = 0; j < n; ++j) {
            double total = 0.0;
            for (size_t k = 0; k < n; ++k) total += a[i*n+k] * b[k*n+j];
            c[i*n+j] = total;
        }
}

void matmul_ikj(const double *a, const double *b, double *c, size_t n) {
    for (size_t i = 0; i < n; ++i)
        for (size_t k = 0; k < n; ++k) {
            double aik = a[i*n+k];
            for (size_t j = 0; j < n; ++j) c[i*n+j] += aik * b[k*n+j];
        }
}
