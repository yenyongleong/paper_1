#ifndef _VISIBILITY_AWARE_SCUBE_H
#define _VISIBILITY_AWARE_SCUBE_H

#include "Scube.h"
#include "../headers/CountMinSketch.h"
#include <random>
#include <chrono>
#include <thread>
#include <cmath>

class VisibilityAwareScube : public Scube {
private:
    Scube* fastPathEngine;       // 公开通道：追求极致速度的原生 Scube
    Scube* securePathEngine;     // 隐私通道：加噪与混淆的 P-Scube
    CountMinSketch preFilter;    // 轻量级预检器，用于快速频率估计
    
    double gamma_priv;           // 隐私阈值系数 (例如 0.005)
    uint32_t window_size;        // 滑动窗口大小 W
    uint32_t current_time_step;  // 当前流处理的时间步

    // 内部简易字符串哈希（用于提取 CMS 键值）
    uint32_t hashString(const string& str) const {
        uint32_t hash = 5381;
        for (char c : str) {
            hash = ((hash << 5) + hash) + c;
        }
        return hash;
    }

    // 生成拉普拉斯噪声 (单调加噪机制)
    double getLaplaceNoise(double lambda) {
        static std::default_random_engine generator(std::chrono::system_clock::now().time_since_epoch().count());
        static std::uniform_real_distribution<double> distribution(-0.5, 0.5);
        double u = distribution(generator);
        return -lambda * (u > 0 ? 1.0 : -1.0) * log(1.0 - 2.0 * abs(u));
    }

    // 模拟动态混淆路由（物理时间侧信道防御）
    void applyNetworkJitter() {
        // 强制引入 100~500 微秒的随机延迟，打破时间与度数的线性相关性
        int jitter_us = 100 + rand() % 400; 
        std::this_thread::sleep_for(std::chrono::microseconds(jitter_us));
    }

public:
    // 构造函数：同时初始化双引擎
    VisibilityAwareScube(uint32_t width, uint32_t depth, uint16_t fplen, double gamma, uint32_t w_size, Scube* fastEngine, Scube* secureEngine)
        : Scube(width, depth, fplen), fastPathEngine(fastEngine), securePathEngine(secureEngine), 
          gamma_priv(gamma), window_size(w_size), current_time_step(0) {
        preFilter.reset();
    }

    ~VisibilityAwareScube() {
        delete fastPathEngine;
        delete securePathEngine;
    }

    // 重写插入逻辑：智能路由核心
    bool insert(string s, string d, w_type w) override {
        current_time_step++;
        uint32_t s_hash = hashString(s);

        // 阶段一：轻量级预检器更新
        preFilter.update(s_hash, 1);

        // 阶段二：动态阈值判定 (γ-Heavy Hitter 模型)
        uint32_t estimated_freq = preFilter.query(s_hash);
        double dynamic_threshold = gamma_priv * window_size;

        bool is_private = (estimated_freq > dynamic_threshold);

        // 阶段三：分流路由与隐私干预
        if (is_private) {
            // [Secure Path - 隐私通道]
            
            // 1. 物理层防御：动态混淆路由
            applyNetworkJitter(); 
            
            // 2. 数据层防御：单调加噪升级 (模拟度数加噪导致的权重放大)
            // 假设噪声比例因子 lambda 为 2.0
            double noise = std::abs(getLaplaceNoise(2.0)); 
            w_type noisy_w = w + static_cast<w_type>(noise);

            // 送入加噪引擎
            return securePathEngine->insert(s, d, noisy_w);
        } else {
            // [Fast Path - 公开通道]
            // 直接送入原生引擎，零延迟，最高效用
            return fastPathEngine->insert(s, d, w);
        }
    }

    // 查询逻辑：整合双通道结果
    w_type edgeWeightQuery(string s, string d) override {
        // 由于边可能被分别路由到了不同的引擎，查询时需整合
        w_type w_fast = fastPathEngine->edgeWeightQuery(s, d);
        w_type w_secure = securePathEngine->edgeWeightQuery(s, d);
        return w_fast + w_secure; // 实际系统可能需要更复杂的去重或合并策略
    }

    // 必须实现的纯虚函数（透传给高速引擎作为默认行为，或合并）
    uint32_t nodeWeightQuery(string v, int type) override {
        return fastPathEngine->nodeWeightQuery(v, type) + securePathEngine->nodeWeightQuery(v, type);
    }
    uint32_t nodeWeightQuery(string v, int type, double& matrix_time, double& addr_time) override {
        return fastPathEngine->nodeWeightQuery(v, type, matrix_time, addr_time);
    }
    void printUsageInfo() override {
        cout << "[Fast Path Engine] "; fastPathEngine->printUsageInfo();
        cout << "[Secure Path Engine] "; securePathEngine->printUsageInfo();
    }
};

#endif // _VISIBILITY_AWARE_SCUBE_H