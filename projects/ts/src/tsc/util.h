#include <random>
#include <chrono>

void ts_util_zero_memory(void *ptr, size_t size)
{
    char *cptr = (char *)ptr;
    for (size_t i = 0; i < size; i++)
    {
        cptr[i] = 0;
    }
}

struct ts_util_random
{
    std::mt19937 generator;
};

void ts_util_init_random(ts_util_random &random)
{
    // finds the time between the system clock
    // (present time) and clock's epoch
    int seed = std::chrono::system_clock::now().time_since_epoch().count();
    
    // mt19937 is a standard mersenne_twister_engine
    random.generator.seed(seed); 
}


int ts_die(ts_util_random &random)
{
    std::uniform_int_distribution<int> distribution(1, 6);
    return distribution(random.generator);
}