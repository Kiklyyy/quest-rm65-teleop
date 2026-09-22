#pragma once

#include <cmath>

namespace rm65_teleop_adapter
{

class QuestInputDeadman
{
public:
  template<typename InputsT>
  bool update(const InputsT & input)
  {
    const float value = static_cast<float>(input.press_middle);
    if (!std::isfinite(value)) {
      pressed_ = false;
    } else if (value >= press_threshold) {
      pressed_ = true;
    } else if (value <= release_threshold) {
      pressed_ = false;
    }
    return pressed_;
  }

  static constexpr float press_threshold{0.60F};
  static constexpr float release_threshold{0.40F};

private:
  bool pressed_{false};
};

}  // namespace rm65_teleop_adapter
