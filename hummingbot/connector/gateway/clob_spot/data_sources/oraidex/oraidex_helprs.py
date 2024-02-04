import asyncio
import traceback


def automatic_retry_with_timeout(retries=0, delay=0, timeout=None):
    def decorator(function):
        async def wrapper(*args, **kwargs):
            errors = []

            for i in range(retries + 1):
                try:
                    result = await asyncio.wait_for(function(*args, **kwargs), timeout=timeout)

                    return result
                except Exception as e:
                    tb_str = traceback.format_exception(type(e), value=e, tb=e.__traceback__)
                    errors.append("".join(tb_str))

                    if i < retries:
                        await asyncio.sleep(delay)

            error_message = f"Function failed after {retries} attempts. Here are the errors:\n" + "\n".join(errors)

            raise Exception(error_message)

        wrapper.original = function

        return wrapper

    return decorator
