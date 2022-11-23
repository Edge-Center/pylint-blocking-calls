from find_blocking_calls import (
    BlockingCallsChecker,
)

# from pylint_plugins.checkers.threads_checker import ThreadsChecker # TODO GCLOUD2-7796: uncomment after fixing
# from pylint_plugins.checkers.db_models_checker import (
#     DBModelsChecker,
# ) # TODO GCLOUD2-7540: uncomment after fixing


def register(linter) -> None:  # pylint: disable=unused-argument
    """
    Required method to register the checker.

    Args:
        linter: Main interface object for Pylint plugins.
    """
    linter.register_checker(BlockingCallsChecker(linter))
    # linter.register_checker(ThreadsChecker(linter)) # TODO GCLOUD2-7796: uncomment after fixing
    # linter.register_checker(DBModelsChecker(linter)) # TODO GCLOUD2-7540: uncomment after fixing
