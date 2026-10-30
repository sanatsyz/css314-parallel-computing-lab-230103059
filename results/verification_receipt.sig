{
  "schema_version": 1,
  "scope": "local_self_check_not_instructor_signature",
  "cryptographically_signed": false,
  "instructor_verifier_available": false,
  "authenticity_limit": "Unsigned local checks and hashes; not an instructor signature or proof of authorship, measurement origin, or timing.",
  "verified_at_utc": "2026-10-30T05:14:56.725841+00:00",
  "student_id": "30103059",
  "environment": {
    "python": "3.14.3",
    "numpy": "2.5.4",
    "platform": "macOS-27.0.1-arm64-arm-64bit-Mach-O"
  },
  "digest_encoding": "SHA-256 of canonical JSON header (scheme local-rounded-array-v1, student_id, shape, decimals=6, dtype=<f8, order=C), NUL, then np.round(array,6) C-order little-endian float64 bytes; signed zero normalized",
  "checks": [
    {
      "milestone": "M0",
      "status": "pass",
      "student_id": "30103059",
      "salted_parameters": {
        "student_id": "30103059",
        "N": 1536,
        "buffer_elements": 16777216,
        "seed": 91405
      },
      "physical_cores": 10,
      "cache_line_bytes": 128,
      "scope": "recorded profile structural consistency; no claim of hardware attestation"
    },
    {
      "milestone": "M1",
      "status": "pass",
      "stride_cases": 8,
      "warmups_per_stride": 5,
      "timed_runs_per_stride": 5,
      "dense_shape": [
        768,
        768
      ],
      "max_absolute_errors": {
        "ijk": 1.1368683772161603e-13,
        "ikj": 1.1368683772161603e-13
      },
      "salted_rounded_sha256": {
        "ijk": "0d276f4bc87d5d1928d548a188f094ca419316165d034251897dae42ba15d2cb",
        "ikj": "0d276f4bc87d5d1928d548a188f094ca419316165d034251897dae42ba15d2cb"
      },
      "numpy_oracle_salted_rounded_sha256": "0d276f4bc87d5d1928d548a188f094ca419316165d034251897dae42ba15d2cb"
    },
    {
      "milestone": "M2",
      "status": "pass",
      "verified_runs": 48,
      "iterations_per_worker": 5000000,
      "worker_counts": [
        1,
        2,
        4,
        8
      ],
      "variants": {
        "unpadded": 8,
        "padded": 128,
        "privatized": 8,
        "padded_64": 64
      },
      "interpretation": "Fixed K per worker is weak scaling; requested Karp-Flatt values are not strong-scaling serial fractions."
    },
    {
      "milestone": "M3",
      "status": "pass",
      "steps": 100,
      "process_counts": [
        1,
        2,
        4,
        8,
        10
      ],
      "verified_arrays": [
        {
          "mode": "strong",
          "workers": 1,
          "shape": [
            1536,
            1536
          ],
          "salted_rounded_sha256": "8f4f99fb2ffbeff4d9791d7981ab7242f246928e83fa1133875d9295b6d906d6",
          "maximum_absolute_error": 0.0
        },
        {
          "mode": "strong",
          "workers": 2,
          "shape": [
            1536,
            1536
          ],
          "salted_rounded_sha256": "8f4f99fb2ffbeff4d9791d7981ab7242f246928e83fa1133875d9295b6d906d6",
          "maximum_absolute_error": 0.0
        },
        {
          "mode": "strong",
          "workers": 4,
          "shape": [
            1536,
            1536
          ],
          "salted_rounded_sha256": "8f4f99fb2ffbeff4d9791d7981ab7242f246928e83fa1133875d9295b6d906d6",
          "maximum_absolute_error": 0.0
        },
        {
          "mode": "strong",
          "workers": 8,
          "shape": [
            1536,
            1536
          ],
          "salted_rounded_sha256": "8f4f99fb2ffbeff4d9791d7981ab7242f246928e83fa1133875d9295b6d906d6",
          "maximum_absolute_error": 0.0
        },
        {
          "mode": "strong",
          "workers": 10,
          "shape": [
            1536,
            1536
          ],
          "salted_rounded_sha256": "8f4f99fb2ffbeff4d9791d7981ab7242f246928e83fa1133875d9295b6d906d6",
          "maximum_absolute_error": 0.0
        },
        {
          "mode": "weak",
          "workers": 1,
          "shape": [
            1536,
            1536
          ],
          "salted_rounded_sha256": "8f4f99fb2ffbeff4d9791d7981ab7242f246928e83fa1133875d9295b6d906d6",
          "maximum_absolute_error": 0.0
        },
        {
          "mode": "weak",
          "workers": 2,
          "shape": [
            2173,
            2173
          ],
          "salted_rounded_sha256": "02c0332ed62a93bfc9e8b9c07a6fb052c19962deaf636537085cdd24df137a64",
          "maximum_absolute_error": 0.0
        },
        {
          "mode": "weak",
          "workers": 4,
          "shape": [
            3072,
            3072
          ],
          "salted_rounded_sha256": "d196ca008c9e6ff1d3926b9cdfba50c9dc079232e30616862476064da93dcc05",
          "maximum_absolute_error": 0.0
        },
        {
          "mode": "weak",
          "workers": 8,
          "shape": [
            4345,
            4345
          ],
          "salted_rounded_sha256": "a235de45cc837b2a8169a33c4d59021973c36c3851622ca929df5d67597572b2",
          "maximum_absolute_error": 0.0
        },
        {
          "mode": "weak",
          "workers": 10,
          "shape": [
            4858,
            4858
          ],
          "salted_rounded_sha256": "e1e53152554a6508d5230337085638c33e056f2ea05ddb9711f4e065dfcfeb5b",
          "maximum_absolute_error": 0.0
        }
      ],
      "amdahl_fit_recomputed": true,
      "gustafson_fit_recomputed": true,
      "roofline_arithmetic_recomputed": true
    }
  ],
  "files": [
    {
      "path": ".gitignore",
      "bytes": 71,
      "sha256": "83c4e73b74b93966ecdb0848eda82f7894ef8e3883ed5fb22ff32da3ba3bc3da"
    },
    {
      "path": "GUIDE.md",
      "bytes": 10424,
      "sha256": "a2fc29c6b4e239755af569d3912d0800472996231f19bd8b1572437057064f9c"
    },
    {
      "path": "HANDOUT_NOTES.md",
      "bytes": 7079,
      "sha256": "fefdc64d4fcd0340f645ae5f1c65a40196842d0a1ed16b6440ab3b98f95d2e4f"
    },
    {
      "path": "ParallelComputingLabPracticum_Paradigm.pdf",
      "bytes": 79306,
      "sha256": "323c32f524da6e5d78ef18daaba43f02d2b6527b9d6aef955f1afed53718f679"
    },
    {
      "path": "README.md",
      "bytes": 1766,
      "sha256": "3a65cd2147a4cab0710d2667c0c5ca08e22850f09dda83e7b927011eec0cc826"
    },
    {
      "path": "requirements-dev.txt",
      "bytes": 34,
      "sha256": "c42c2e22023f8aaa0ad5e8b410b63b9aa1e44908f297d6fcebd5c2878c8a04dd"
    },
    {
      "path": "requirements.txt",
      "bytes": 14,
      "sha256": "8f40ca44a22b1aa83e698b44fe63c246695b49eb7e4a12b9de93c2276c0d62f9"
    },
    {
      "path": "results/arrays/dense_a.npy",
      "bytes": 4718720,
      "sha256": "8c6e818f1cf97ed007a5689c155f6c4e33c20ffde91efeeaa3bfbb09cc13fa7a"
    },
    {
      "path": "results/arrays/dense_b.npy",
      "bytes": 4718720,
      "sha256": "d6f1b61ad20c6dfd844350ba74ed0cbd0079406cd717619490ce2e6ed397ea56"
    },
    {
      "path": "results/arrays/dense_ijk.npy",
      "bytes": 4718720,
      "sha256": "1c2988993b2bb752876361de14036caec54979d385ea188ef58925fb97e4d23c"
    },
    {
      "path": "results/arrays/dense_ikj.npy",
      "bytes": 4718720,
      "sha256": "1c2988993b2bb752876361de14036caec54979d385ea188ef58925fb97e4d23c"
    },
    {
      "path": "results/arrays/scaling_strong_p1/manifest.json",
      "bytes": 841,
      "sha256": "58555dd4a3f3071fd6f2f7f4b88a839aa7026fe6f594df3b9994acfd011c94e2"
    },
    {
      "path": "results/arrays/scaling_strong_p1/part-0000.npz",
      "bytes": 15050333,
      "sha256": "3e75942fc788695fbcd635b009fea8d6b090d919af72554f607d7271ff5c3497"
    },
    {
      "path": "results/arrays/scaling_strong_p1/part-0001.npz",
      "bytes": 1877449,
      "sha256": "e424f07157b6866a09d0f7459356543b30dbfa99cf9c7a133ca25700ef889b77"
    },
    {
      "path": "results/arrays/scaling_strong_p10/manifest.json",
      "bytes": 841,
      "sha256": "58555dd4a3f3071fd6f2f7f4b88a839aa7026fe6f594df3b9994acfd011c94e2"
    },
    {
      "path": "results/arrays/scaling_strong_p10/part-0000.npz",
      "bytes": 15050333,
      "sha256": "3e75942fc788695fbcd635b009fea8d6b090d919af72554f607d7271ff5c3497"
    },
    {
      "path": "results/arrays/scaling_strong_p10/part-0001.npz",
      "bytes": 1877449,
      "sha256": "e424f07157b6866a09d0f7459356543b30dbfa99cf9c7a133ca25700ef889b77"
    },
    {
      "path": "results/arrays/scaling_strong_p2/manifest.json",
      "bytes": 841,
      "sha256": "58555dd4a3f3071fd6f2f7f4b88a839aa7026fe6f594df3b9994acfd011c94e2"
    },
    {
      "path": "results/arrays/scaling_strong_p2/part-0000.npz",
      "bytes": 15050333,
      "sha256": "3e75942fc788695fbcd635b009fea8d6b090d919af72554f607d7271ff5c3497"
    },
    {
      "path": "results/arrays/scaling_strong_p2/part-0001.npz",
      "bytes": 1877449,
      "sha256": "e424f07157b6866a09d0f7459356543b30dbfa99cf9c7a133ca25700ef889b77"
    },
    {
      "path": "results/arrays/scaling_strong_p4/manifest.json",
      "bytes": 841,
      "sha256": "58555dd4a3f3071fd6f2f7f4b88a839aa7026fe6f594df3b9994acfd011c94e2"
    },
    {
      "path": "results/arrays/scaling_strong_p4/part-0000.npz",
      "bytes": 15050333,
      "sha256": "3e75942fc788695fbcd635b009fea8d6b090d919af72554f607d7271ff5c3497"
    },
    {
      "path": "results/arrays/scaling_strong_p4/part-0001.npz",
      "bytes": 1877449,
      "sha256": "e424f07157b6866a09d0f7459356543b30dbfa99cf9c7a133ca25700ef889b77"
    },
    {
      "path": "results/arrays/scaling_strong_p8/manifest.json",
      "bytes": 841,
      "sha256": "58555dd4a3f3071fd6f2f7f4b88a839aa7026fe6f594df3b9994acfd011c94e2"
    },
    {
      "path": "results/arrays/scaling_strong_p8/part-0000.npz",
      "bytes": 15050333,
      "sha256": "3e75942fc788695fbcd635b009fea8d6b090d919af72554f607d7271ff5c3497"
    },
    {
      "path": "results/arrays/scaling_strong_p8/part-0001.npz",
      "bytes": 1877449,
      "sha256": "e424f07157b6866a09d0f7459356543b30dbfa99cf9c7a133ca25700ef889b77"
    },
    {
      "path": "results/arrays/scaling_weak_p1/manifest.json",
      "bytes": 841,
      "sha256": "58555dd4a3f3071fd6f2f7f4b88a839aa7026fe6f594df3b9994acfd011c94e2"
    },
    {
      "path": "results/arrays/scaling_weak_p1/part-0000.npz",
      "bytes": 15050333,
      "sha256": "3e75942fc788695fbcd635b009fea8d6b090d919af72554f607d7271ff5c3497"
    },
    {
      "path": "results/arrays/scaling_weak_p1/part-0001.npz",
      "bytes": 1877449,
      "sha256": "e424f07157b6866a09d0f7459356543b30dbfa99cf9c7a133ca25700ef889b77"
    },
    {
      "path": "results/arrays/scaling_weak_p10/manifest.json",
      "bytes": 3257,
      "sha256": "77857e825cdd050cb7597728d27ea69b3a8d804d13ba4b3eed5448a55bd6a2e3"
    },
    {
      "path": "results/arrays/scaling_weak_p10/part-0000.npz",
      "bytes": 14996606,
      "sha256": "946b2c5ce46126935907c0152028445688dcf91c0fc8ef0c63e3df61395d445f"
    },
    {
      "path": "results/arrays/scaling_weak_p10/part-0001.npz",
      "bytes": 15032137,
      "sha256": "68c2066493317a92f3a957750d614755e016cbd5326c91297b316054bd7afe78"
    },
    {
      "path": "results/arrays/scaling_weak_p10/part-0002.npz",
      "bytes": 15040850,
      "sha256": "42d2480a6b7b6bbaf9907f06063d44ac28d508346b6d3cb5bc2e11a83cdf26c1"
    },
    {
      "path": "results/arrays/scaling_weak_p10/part-0003.npz",
      "bytes": 15033990,
      "sha256": "a8dec5fe10d0eaa1d724c4feaa42f18be8f301f921e91a7a806f8a974ad97fbc"
    },
    {
      "path": "results/arrays/scaling_weak_p10/part-0004.npz",
      "bytes": 15035755,
      "sha256": "982eb6ba8a75b1f539f5d6ff426d4839b99cb0fc675c010dd0feb9f0e747d1ab"
    },
    {
      "path": "results/arrays/scaling_weak_p10/part-0005.npz",
      "bytes": 15034719,
      "sha256": "899ec46f2299bd9fd9deaa747a21ea322ab81b09c37725cc81e6b43fd5cd0d94"
    },
    {
      "path": "results/arrays/scaling_weak_p10/part-0006.npz",
      "bytes": 15034601,
      "sha256": "06bcc4d0fdffa798b70787b43ec42daed5e7ab51ed01dc0a17c8ae153b0f11f5"
    },
    {
      "path": "results/arrays/scaling_weak_p10/part-0007.npz",
      "bytes": 15034828,
      "sha256": "471101aacd0f029e6ba945893676d1cd0721e6e78823a05ba893753761bd2cdf"
    },
    {
      "path": "results/arrays/scaling_weak_p10/part-0008.npz",
      "bytes": 15030373,
      "sha256": "57f182226814713770d94f10f3cc4802fcd874621db26c396aedcc4a0089f946"
    },
    {
      "path": "results/arrays/scaling_weak_p10/part-0009.npz",
      "bytes": 15029440,
      "sha256": "fa823abc9c0da97686805be7220495bd9249cbff0ba609ad5243b99926c6b38c"
    },
    {
      "path": "results/arrays/scaling_weak_p10/part-0010.npz",
      "bytes": 15033253,
      "sha256": "d202c84e4151a945a0c87794ee026a3bd0ca2281b875898701c0a53064c1239e"
    },
    {
      "path": "results/arrays/scaling_weak_p10/part-0011.npz",
      "bytes": 4048364,
      "sha256": "bc59f70ed442d924dec077c9fdd8770d8119602ced3c29495803c9add6b358a5"
    },
    {
      "path": "results/arrays/scaling_weak_p2/manifest.json",
      "bytes": 1081,
      "sha256": "52c870fbce7ca11b7d2b275ad10772e4f01f7755e95caf30fa5f907ed60f3585"
    },
    {
      "path": "results/arrays/scaling_weak_p2/part-0000.npz",
      "bytes": 15045254,
      "sha256": "59b4b66b72c8b1accb342499971be9473695d43e08356684d5c929f7d41922b9"
    },
    {
      "path": "results/arrays/scaling_weak_p2/part-0001.npz",
      "bytes": 15060954,
      "sha256": "f5a7efd0f70a74ec3d7af87c88f946bb7d787d369584d6ef08a8a33fc4a81f9f"
    },
    {
      "path": "results/arrays/scaling_weak_p2/part-0002.npz",
      "bytes": 3778953,
      "sha256": "201137387e34403e7e19cdc296ebe897f0666ee29ca4fce190ebff4bc4366cb4"
    },
    {
      "path": "results/arrays/scaling_weak_p4/manifest.json",
      "bytes": 1565,
      "sha256": "b1ba3088bb262229b5f51ce9404f0586c30ade897e892beebd78ad0b92e26f0b"
    },
    {
      "path": "results/arrays/scaling_weak_p4/part-0000.npz",
      "bytes": 15022024,
      "sha256": "db3617b7d0b7e174f520dc65e6ae10af861db4f9f7233dcdba17f8630e64f914"
    },
    {
      "path": "results/arrays/scaling_weak_p4/part-0001.npz",
      "bytes": 15041779,
      "sha256": "42341526bab1da8204e38a223491208e93053acf37e784158fa63a50af945ddd"
    },
    {
      "path": "results/arrays/scaling_weak_p4/part-0002.npz",
      "bytes": 15043736,
      "sha256": "f9b722d0bb04b32fa66307909d6927957b570bdb3e699420c5a4218208b9634a"
    },
    {
      "path": "results/arrays/scaling_weak_p4/part-0003.npz",
      "bytes": 15047886,
      "sha256": "0b5179f25cc0a37c689f68e77570f66f790eefa03f9a4b1eb785193760ae48dc"
    },
    {
      "path": "results/arrays/scaling_weak_p4/part-0004.npz",
      "bytes": 7569980,
      "sha256": "8b64fd03dad7d4cc4328969536e23921bc4d44ea846dfd2da82812a5048a1717"
    },
    {
      "path": "results/arrays/scaling_weak_p8/manifest.json",
      "bytes": 2772,
      "sha256": "c38a08fac07555ba3206b1d00389fc2035eed1b15e598e3b746c056e4f2103ee"
    },
    {
      "path": "results/arrays/scaling_weak_p8/part-0000.npz",
      "bytes": 15013019,
      "sha256": "00b2dd2b190087eac9768993062ae0fa055a6af0d1340e556736ae9573e9471f"
    },
    {
      "path": "results/arrays/scaling_weak_p8/part-0001.npz",
      "bytes": 15038736,
      "sha256": "294667f4c095d9173efff962e3cec3351732ab3824a75639dd2171ef80cd4123"
    },
    {
      "path": "results/arrays/scaling_weak_p8/part-0002.npz",
      "bytes": 15036955,
      "sha256": "1ee1fdff2573e0be893b597b46305ff4c8f369d0cded1f004bb1a35f4341aead"
    },
    {
      "path": "results/arrays/scaling_weak_p8/part-0003.npz",
      "bytes": 15034636,
      "sha256": "dc2f4373d342aeb62b3612586a4e3cc8e8ff25761b4197763081fd4ea4b77ea5"
    },
    {
      "path": "results/arrays/scaling_weak_p8/part-0004.npz",
      "bytes": 15038605,
      "sha256": "d4733dbe26b503a9e00e1730b96d14f8e6fca4e14aaaf7bbd5df9375b8b871de"
    },
    {
      "path": "results/arrays/scaling_weak_p8/part-0005.npz",
      "bytes": 15029914,
      "sha256": "efd46170d380da8af8440fb2949994bc1b57d8a6999622a88f1d75e73ac4e555"
    },
    {
      "path": "results/arrays/scaling_weak_p8/part-0006.npz",
      "bytes": 15035399,
      "sha256": "5d7578f6183e17e41e7760fed2303c568dbd2774fff85cc2f99b6af9e85ee3e0"
    },
    {
      "path": "results/arrays/scaling_weak_p8/part-0007.npz",
      "bytes": 15040963,
      "sha256": "9afbfe967447f1c207f9ac218233594a41a01a4729dd97a3d3f3c5c6bd116268"
    },
    {
      "path": "results/arrays/scaling_weak_p8/part-0008.npz",
      "bytes": 15040152,
      "sha256": "24e6241bed6a72ba6a5f88d18ca81543cf7279d9fda20a0b7d51d56035039b84"
    },
    {
      "path": "results/arrays/scaling_weak_p8/part-0009.npz",
      "bytes": 189242,
      "sha256": "706242e4132c698970f908e7bdf6b521bf7f8402834389a7577074a12ae8c8d6"
    },
    {
      "path": "results/false_sharing_karp_flatt.tsv",
      "bytes": 3355,
      "sha256": "de28e836b672f45de4dac29d018be3b049e5078e6d0462f87be9cbd50afdd90b"
    },
    {
      "path": "results/false_sharing_raw.json",
      "bytes": 75785,
      "sha256": "93da19a3f281d19171b6bdf582131fd8d21492c88d5b5f5c71f9a644a6103987"
    },
    {
      "path": "results/host_profile.json",
      "bytes": 1578,
      "sha256": "26118c241718f983367a6f8dfa18919d05b1cce238ff43cccf855276a42e3acc"
    },
    {
      "path": "results/loop_interchange.json",
      "bytes": 1097,
      "sha256": "0bf4496a80f1ae7fac83d94d23fd0aa1ee785e86bc41d039dc5aa358070ca13f"
    },
    {
      "path": "results/reproducibility.json",
      "bytes": 1124,
      "sha256": "aaf9cc7561b9f60d236298c48e108dc61d7a6109a5af5278bc47403af84b3d3f"
    },
    {
      "path": "results/roofline_summary.json",
      "bytes": 10588,
      "sha256": "8e9ded8f8e81bdf29feef77ae38750f4b8e4f6f1b64fd8fa8d72c6384b2bf946"
    },
    {
      "path": "results/salted_params.json",
      "bytes": 92,
      "sha256": "cf6f35326635df53514da11f43d407801eaaa28bd6da4622c7c863a1ef59f29e"
    },
    {
      "path": "results/scaling_metrics.tsv",
      "bytes": 2226,
      "sha256": "4ca6f194fa13c651bcfe9baf17e3e7cb08d0113c4a16955985a07472fa21a8d5"
    },
    {
      "path": "results/scaling_raw.json",
      "bytes": 30729,
      "sha256": "a68763f8f4fdcbad16690f06f161d8a40ab18169aeab670c89c0f85a5b0673a5"
    },
    {
      "path": "results/stride_raw.json",
      "bytes": 3098,
      "sha256": "5c7f8fd19a8bc9dcc462f92e5b7fdcf189603cb97c19279996fc3e508d0f3604"
    },
    {
      "path": "results/stride_results.tsv",
      "bytes": 489,
      "sha256": "d9a4daf2d6bc4e838f5bc5c208ab3c685bc5543ac8f54cd276b18480e69c7b72"
    },
    {
      "path": "run_lab.py",
      "bytes": 1415,
      "sha256": "7ed9b4dc1a9c1271865d49e49ffb0cd07bace8e01394962a3a4b0d2e752872d6"
    },
    {
      "path": "src/dense_kernel.py",
      "bytes": 3537,
      "sha256": "37b16b45a6656942f73395f38328879408a5dd4a154172dd5875ee3b737bdc79"
    },
    {
      "path": "src/false_sharing.py",
      "bytes": 18693,
      "sha256": "a30f32c102e5fb5904ad47e60ffb6caccecdf9265c5b28e10f26ca75f445206d"
    },
    {
      "path": "src/locality_native.py",
      "bytes": 1563,
      "sha256": "3c4177b8a8aca7b52b0d770e01761319b769e86356187ff003b3fe1100dcaf52"
    },
    {
      "path": "src/native/false_sharing.c",
      "bytes": 740,
      "sha256": "7240d44766e1ff230d9e3a557d2f4821f26f7f1de9d4707d2ee535ad1faa3493"
    },
    {
      "path": "src/native/locality.c",
      "bytes": 885,
      "sha256": "9d4645d1f6247eb04468c8131169da93fa789550e6463b10e2d0e23248fc0801"
    },
    {
      "path": "src/profile_env.py",
      "bytes": 4948,
      "sha256": "d73347df6795f967bb95bd21d8ab1aad1d239b76451eea3a7d3c6d9ea1272e1f"
    },
    {
      "path": "src/salt.py",
      "bytes": 503,
      "sha256": "486ade22b6bba32f691efe8a6967dfdb6f6a6def7d4b1121953f13adb438d5b2"
    },
    {
      "path": "src/scaling_study.py",
      "bytes": 29911,
      "sha256": "b3389b56fb8925fdb5a6450e2521bbe56824b4e51e88cb4b22701dbf93864d59"
    },
    {
      "path": "src/stride_bench.py",
      "bytes": 2766,
      "sha256": "5aca3fa69cb1b7258012919c773f025a7badf66e3b625ff810782614af45a0b7"
    },
    {
      "path": "tests/test_false_sharing.py",
      "bytes": 2946,
      "sha256": "0ccb7560150ec59c023c16edd1340513a7586d3118b78301c47519a8f024c9ca"
    },
    {
      "path": "tests/test_locality.py",
      "bytes": 4527,
      "sha256": "df06449c1aa8b25b7d15ee7b243f61546466a5d7d9db3a58ad107a561e721154"
    },
    {
      "path": "tests/test_scaling.py",
      "bytes": 5929,
      "sha256": "dfa2aa5e9a1d373c7935141a663660a1eed512c8c63f0524f5160e1c482dd978"
    },
    {
      "path": "tests/test_verifier.py",
      "bytes": 4582,
      "sha256": "4344be3522462856ad4c85a6490d0b1a063d899fd44a351e03eabae3344db86a"
    },
    {
      "path": "verify_outputs.py",
      "bytes": 30283,
      "sha256": "f1cccfc8c9d19b6814c912388a33d6f1033f9c2cb23699bd7d906698a1a76582"
    }
  ],
  "manifest_exclusions": [
    "verification_receipt.sig itself",
    "__pycache__ and .pyc runtime caches"
  ]
}
