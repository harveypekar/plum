#include "types.h"
#include "utest.h"

UTEST_MAIN()

UTEST(init, fields)
{
    ts_state state = ts_create_state();
    state = ts_advance_game(state);

    ASSERT_EQ(state._current_step, TS_STEP_INIT);
    ASSERT_EQ(state.turn, 1);
    ASSERT_EQ(state.ar, 1);
    ASSERT_EQ(state.defcon, 5);
    ASSERT_EQ(state.vp, 0);
    ASSERT_EQ(state.mil[TS_US], 0);
    ASSERT_EQ(state.mil[TS_USSR], 0);
    ASSERT_EQ(state.phasing, TS_US);
    ASSERT_EQ(state.china_card_state, TS_CHINA_CARD_STATE_USSR_FACEUP);

    
}

