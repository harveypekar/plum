#include "types.h"
#include <cassert>
#include <cstdio>

void test_country_count()
{
    assert(ts_country_amount == 87);
    printf("PASS: country count = %d\n", ts_country_amount);
}

void test_battleground_count()
{
    int bg = 0;
    for (int i = 0; i < ts_country_amount; i++)
        if (ts_countries[i].battleground)
            bg++;
    assert(bg == 29);
    printf("PASS: battleground count = %d\n", bg);
}

void test_card_count()
{
    assert(ts_card_amount > 0);
    printf("PASS: card count = %d\n", ts_card_amount);
}

void test_france_is_battleground()
{
    for (int i = 0; i < ts_country_amount; i++)
    {
        if (ts_countries[i].id == TS_FRANCE)
        {
            assert(ts_countries[i].battleground == true);
            assert(ts_countries[i].stability == 3);
            printf("PASS: France is BG with stability 3\n");
            return;
        }
    }
    assert(false && "France not found");
}

int main()
{
    test_country_count();
    test_battleground_count();
    test_card_count();
    test_france_is_battleground();
    printf("\nAll tests passed.\n");
    return 0;
}
